import logging
from pathlib import Path
from typing import Dict, List, Optional

from models.table_access_info import TableAccessInfo
from models.modification_context import ModificationContext
from modifier.context_generator.base_context_generator import BaseContextGenerator
from parser.java_ast_parser import JavaASTParser

logger = logging.getLogger(__name__)


class AnyframeContextGenerator(BaseContextGenerator):
    """
    Anyframe Context Generator

    PURPOSE:
    Groups files from layer_files based on their actual code relationships (imports).
    We already have ALL files from upstream analyzer - we're just organizing them into
    logical batches based on which files actually call which other files.

    ARCHITECTURE (confirmed from code analysis):
        SVC (Service) - highest layer, anchor point
         ↓ creates/uses
        BIZ (Business logic)
         ↓ uses
        DQM/DEM (Data access)

    PROCESS:
    1. Start with each SVC file (anchor)
    2. Parse its imports to see which BIZ/DQM/DEM files IT uses
    3. Parse those matched files to see which VOs THEY use (import chain)
    4. Group: [SVC + its matched files] as modification targets
             [relevant VOs] as context only
    5. Create one batch per SVC with only its related files

    This ensures clean, focused batches instead of dumping all files together.
    """

    # VO 파일 최대 토큰 예산 (MybatisContextGenerator와 동일)
    MAX_VO_TOKENS = 80000

    # 토큰 제한 사용 여부 (False로 설정하면 모든 VO 파일 포함)
    USE_TOKEN_LIMIT = True  # Set to False to disable token limit

    def _get_package_from_file(self, file_path: str) -> Optional[str]:
        """
        파일에서 package 선언을 추출합니다.

        예: package sli.gps.ia.ofr.biz; → "sli.gps.ia.ofr.biz"
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("package ") and line.endswith(";"):
                        # package sli.gps.ia.ofr.biz; → sli.gps.ia.ofr.biz
                        return line[8:-1].strip()
        except Exception as e:
            logger.warning(f"패키지 추출 실패: {file_path} - {e}")
        return None

    def _infer_base_src_path(self, layer_files: Dict[str, List[str]]) -> Optional[str]:
        """
        layer_files에서 base source path를 추론합니다.

        예: /project/src/main/java/sli/gps/biz/UserBIZ.java
            package: sli.gps.biz
            → base: /project/src/main/java
        """
        # 모든 레이어에서 첫 번째 파일 찾기
        for layer_name, files in layer_files.items():
            if files:
                sample_file = files[0]
                package = self._get_package_from_file(sample_file)
                if package:
                    # package를 경로로 변환
                    package_path = package.replace(".", "/")

                    # 파일 경로에서 package 경로 제거
                    file_path_normalized = str(Path(sample_file)).replace("\\", "/")

                    # base path 추출
                    if package_path in file_path_normalized:
                        idx = file_path_normalized.rfind(package_path)
                        base_path = file_path_normalized[:idx]
                        return base_path

        logger.warning("Base source path를 추론할 수 없습니다")
        return None

    def _convert_import_to_file_path(
        self, import_statement: str, base_src_path: str
    ) -> Optional[str]:
        """
        Import 문을 파일 경로로 변환합니다.

        Args:
            import_statement: 예: "sli.gps.ia.ofr.biz.BCUserInfoBIZ"
            base_src_path: 예: "/project/src/main/java/"

        Returns:
            예: "/project/src/main/java/sli/gps/ia/ofr/biz/BCUserInfoBIZ.java"
        """
        if not base_src_path:
            return None

        # import를 경로로 변환
        package_path = import_statement.replace(".", "/")
        full_path = Path(base_src_path) / f"{package_path}.java"

        # 파일 존재 확인
        if full_path.exists():
            return str(full_path)

        return None

    def _find_biz_chain_to_target(
        self,
        biz_file: str,
        base_src_path: str,
        biz_files: List[str],
        target_dqm_files: List[str],
        target_dem_files: List[str],
        java_parser,
        visited: set,
        chain: List[str],
    ) -> Optional[List[str]]:
        """
        BIZ 파일에서 시작하여 target DQM/DEM까지의 체인을 찾습니다.

        재귀적으로 BIZ → BIZ → ... → DQM/DEM 경로를 탐색하며,
        target DQM/DEM을 발견하면 전체 체인을 반환합니다.

        Args:
            biz_file: 현재 BIZ 파일 경로
            base_src_path: 소스 base 경로
            biz_files: layer_files의 BIZ 목록
            target_dqm_files: 타겟 DQM 파일 목록 (우리 테이블 접근하는 것만)
            target_dem_files: 타겟 DEM 파일 목록 (우리 테이블 접근하는 것만)
            java_parser: Java 파서
            visited: 이미 방문한 BIZ 파일 (무한 루프 방지)
            chain: 현재까지의 BIZ 체인

        Returns:
            타겟까지의 전체 BIZ 체인, 또는 None (타겟 없음)
        """
        if biz_file in visited:
            return None

        visited.add(biz_file)
        current_chain = chain + [biz_file]

        # BVO 파일 제외
        if biz_file.endswith("BVO.java"):
            return None

        try:
            # BIZ 파일 파싱
            biz_tree, biz_error = java_parser.parse_file(Path(biz_file))
            if biz_error:
                return None

            biz_classes = java_parser.extract_class_info(biz_tree, Path(biz_file))
            if not biz_classes:
                return None

            biz_class = next(
                (c for c in biz_classes if c.access_modifier == "public"),
                biz_classes[0],
            )
            biz_imports = set(biz_class.imports)

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # STOP CONDITION: 타겟 DQM/DEM 발견!
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            for imp in biz_imports:
                # 타겟 DQM 발견
                if self._match_import_to_file_path(imp, target_dqm_files):
                    return current_chain  # 전체 체인 반환!

                # 타겟 DEM 발견
                if self._match_import_to_file_path(imp, target_dem_files):
                    return current_chain  # 전체 체인 반환!

            # Same-package에서도 DQM/DEM 확인
            same_package_dqm = self._find_same_package_references(
                biz_file, target_dqm_files
            )
            if same_package_dqm:
                return current_chain

            same_package_dem = self._find_same_package_references(
                biz_file, target_dem_files
            )
            if same_package_dem:
                return current_chain

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 타겟 못 찾음 → 더 깊이 들어가기 (BIZ → BIZ)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            # Import로 찾기
            for imp in biz_imports:
                # 다른 BIZ 찾기
                nested_biz = self._match_import_to_file_path(imp, biz_files)
                if nested_biz:
                    result = self._find_biz_chain_to_target(
                        nested_biz,
                        base_src_path,
                        biz_files,
                        target_dqm_files,
                        target_dem_files,
                        java_parser,
                        visited,
                        current_chain,
                    )
                    if result:
                        return result  # 타겟 찾음!

            # Same-package BIZ 찾기
            same_package_biz = self._find_same_package_references(biz_file, biz_files)
            for nested_biz in same_package_biz:
                result = self._find_biz_chain_to_target(
                    nested_biz,
                    base_src_path,
                    biz_files,
                    target_dqm_files,
                    target_dem_files,
                    java_parser,
                    visited,
                    current_chain,
                )
                if result:
                    return result  # 타겟 찾음!

            # Fallback: layer_files에 없는 BIZ도 확인
            for imp in biz_imports:
                if "biz" not in imp.lower() and "BIZ" not in imp:
                    continue

                # Import → 파일 경로 변환
                nested_biz_path = self._convert_import_to_file_path(imp, base_src_path)
                if nested_biz_path and nested_biz_path not in visited:
                    result = self._find_biz_chain_to_target(
                        nested_biz_path,
                        base_src_path,
                        biz_files,
                        target_dqm_files,
                        target_dem_files,
                        java_parser,
                        visited,
                        current_chain,
                    )
                    if result:
                        return result  # 타겟 찾음!

            # 타겟 못 찾음
            return None

        except Exception as e:
            logger.debug(f"      BIZ chain 탐색 실패: {Path(biz_file).name} - {e}")
            return None

    def _find_same_package_references(
        self, current_file: str, all_files_in_layer: List[str]
    ) -> List[str]:
        """
        같은 패키지에 있는 파일들 중 현재 파일에서 참조되는 것을 찾습니다.

        이는 import 없이 사용되는 same-package 클래스를 찾기 위한 것입니다.
        예: private IAOfrCaseMngBIZ caseMngBIZ = new IAOfrCaseMngBIZ();

        Args:
            current_file: 현재 파일 경로
            all_files_in_layer: 같은 레이어의 모든 파일 목록 (예: biz_files)

        Returns:
            현재 파일에서 참조되는 같은 패키지 파일들
        """
        referenced_files: List[str] = []

        # 1. 현재 파일의 패키지 추출
        current_package = self._get_package_from_file(current_file)
        if not current_package:
            return []

        # 2. 같은 패키지에 있는 다른 파일들 찾기
        same_package_files = []
        for file_path in all_files_in_layer:
            if file_path == current_file:  # 자기 자신 제외
                continue

            file_package = self._get_package_from_file(file_path)
            if file_package == current_package:
                same_package_files.append(file_path)

        if not same_package_files:
            return []

        # 3. 현재 파일 내용 읽기
        try:
            with open(current_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"파일 읽기 실패: {current_file} - {e}")
            return []

        # 4. 각 same-package 파일의 클래스명이 현재 파일에 있는지 확인
        for file_path in same_package_files:
            class_name = Path(file_path).stem  # IAOfrCaseMngBIZ.java → IAOfrCaseMngBIZ

            # 단순 문자열 검색 (빠르고 정확!)
            if class_name in content:
                referenced_files.append(file_path)

        return referenced_files

    def _match_import_to_file_path(
        self, import_statement: str, target_files: List[str]
    ) -> Optional[str]:
        """
        import 문과 일치하는 파일을 target_files에서 찾습니다.

        NOTE: target_files는 이미 upstream에서 제공된 파일들입니다.
        우리는 새로운 파일을 찾는 게 아니라, 주어진 파일 중에서
        이 import와 매칭되는 파일을 찾는 것입니다.

        Args:
            import_statement: Java import 문 (예: "sli.gps.bc.biz.UserBIZ")
            target_files: 매칭 대상 파일 목록 (layer_files에서 가져온 것)

        Returns:
            매칭되는 파일 경로, 없으면 None
        """
        expected_path_parts = import_statement.split(".")
        expected_class_name = expected_path_parts[-1]

        for file_path in target_files:
            file_path_obj = Path(file_path)

            # 1. 클래스명 확인 (빠른 필터링)
            if file_path_obj.stem != expected_class_name:
                continue

            # 2. Windows 경로 정규화
            normalized_path = str(file_path_obj).replace("\\", "/")
            file_parts = normalized_path.split("/")

            # 3. Package 경로가 파일 경로에 순서대로 포함되는지 확인
            # 예: sli.gps.bc.biz.UserBIZ → .../sli/gps/bc/biz/UserBIZ.java
            match_found = False
            for i in range(len(file_parts) - len(expected_path_parts) + 1):
                if all(
                    file_parts[i + j] == expected_path_parts[j]
                    for j in range(len(expected_path_parts) - 1)
                ):
                    if file_path_obj.stem == expected_class_name:
                        match_found = True
                        break

            if match_found:
                return file_path

        return None

    def _select_vo_files_by_token_budget(
        self,
        vo_files: List[str],
        all_imports: set,
        max_tokens: int,
    ) -> List[str]:
        """
        토큰 예산 내에서 VO 파일을 선택합니다.

        OPTIMIZATION:
        - USE_TOKEN_LIMIT=False: 파일 읽지 않고 import 매칭만 (빠름!)
        - USE_TOKEN_LIMIT=True: 파일 읽고 토큰 계산 (느림)

        Args:
            vo_files: 전체 VO 파일 목록
            all_imports: 모든 레이어의 import 문
            max_tokens: 최대 토큰 예산

        Returns:
            선택된 VO 파일 목록
        """
        selected_files: List[str] = []
        current_tokens = 0

        # ====== FAST PATH: 토큰 제한 없을 때 ======
        if not self.USE_TOKEN_LIMIT:
            for imp in all_imports:
                matched = self._match_import_to_file_path(imp, vo_files)
                if matched and matched not in selected_files:
                    selected_files.append(matched)

            logger.info(f"VO 파일 선택 완료: {len(selected_files)}개")
            return selected_files

        # ====== SLOW PATH: 토큰 제한 있을 때 ======
        for imp in all_imports:
            matched = self._match_import_to_file_path(imp, vo_files)
            if matched and matched not in selected_files:
                try:
                    with open(matched, "r", encoding="utf-8") as f:
                        content = f.read()
                    file_tokens = self._calculate_token_size(content)

                    if current_tokens + file_tokens <= max_tokens:
                        selected_files.append(matched)
                        current_tokens += file_tokens
                    else:
                        # 예산 초과 시 조기 종료 (최적화)
                        break
                except Exception as e:
                    logger.warning(f"VO 파일 읽기 실패: {matched} - {e}")

        logger.info(
            f"VO 파일 선택 완료: {len(selected_files)}개, "
            f"총 {current_tokens:,} tokens (예산: {max_tokens:,})"
        )

        return selected_files

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
        table_access_info: Optional[TableAccessInfo] = None,
        endpoint_method: Optional[str] = None,
    ) -> List[ModificationContext]:
        """
        SVC 파일을 anchor로 삼아 관련 파일들을 그룹화하여 배치를 생성합니다.

        핵심 개념:
        - layer_files에는 이미 모든 파일이 들어있음 (upstream analyzer가 찾음)
        - 우리의 역할: 이 파일들을 import 관계에 따라 논리적 그룹으로 나누기
        - 각 SVC별로 하나의 배치 생성 (SVC + 그것이 사용하는 파일들)

        Args:
            layer_files: 레이어별 파일 목록 (upstream에서 제공)
                - "svc": Service 파일들
                - "biz": Business logic 파일들
                - "repository": VO/SVO/DVO 파일들
                - "dem_daq": DQM/DEM 파일들
            table_name: 테이블 이름
            columns: 컬럼 목록
            table_access_info: 테이블 접근 정보
            endpoint_method: 엔드포인트 메소드

        Returns:
            생성된 ModificationContext 배치 목록
        """
        all_batches: List[ModificationContext] = []

        # ═══════════════════════════════════════════════════════════════
        # STEP 1: 레이어별 파일 추출 및 정리
        # ═══════════════════════════════════════════════════════════════

        svc_files_raw = layer_files.get("svc", [])
        biz_files = layer_files.get("biz", [])
        repository_files = layer_files.get("Repository", [])
        dem_daq_files = layer_files.get("dem_daq", [])

        # SVC 파일에서 실제 Service 구현만 필터링 (VO 파일 제외)
        svc_files_all = [
            x
            for x in svc_files_raw
            if not (
                x.endswith("VO.java")
                or x.endswith("SVO.java")
                or x.endswith("DVO.java")
            )
        ]

        # ServiceImpl 파일과 Interface 파일 분리
        svc_impl_files = [x for x in svc_files_all if x.endswith("Impl.java")]
        svc_interface_files = [x for x in svc_files_all if not x.endswith("Impl.java")]

        # ServiceImpl → Interface 페어링 (역방향: Impl에서 Interface 찾기)
        # 패턴: IAOfrCaseInfoMngSVCImpl.java → IIAOfrCaseInfoMngSVC.java
        impl_to_interface: Dict[str, str] = {}

        for impl_file in svc_impl_files:
            impl_path = Path(impl_file)
            # Impl 제거: IAOfrCaseInfoMngSVCImpl → IAOfrCaseInfoMngSVC or IIAOfrCaseInfoMngSVC
            interface_name_candidate1 = impl_path.stem.replace("Impl", "") + ".java"
            interface_name_candidate2 = (
                "I" + impl_path.stem.replace("Impl", "") + ".java"
            )

            # 같은 디렉토리 또는 상위 디렉토리에서 Interface 찾기
            possible_interface_path1 = (
                impl_path.parent.parent / interface_name_candidate1
            )
            possible_interface_path2 = (
                impl_path.parent.parent / interface_name_candidate2
            )

            for candidate_path in [possible_interface_path1, possible_interface_path2]:
                if candidate_path.exists():
                    interface_file_str = str(candidate_path)
                    if interface_file_str in svc_interface_files:
                        impl_to_interface[impl_file] = interface_file_str
                        break

        # ===== 핵심: ServiceImpl을 anchor로 사용 =====
        # Interface가 없는 Impl도 처리할 수 있도록
        anchor_files = svc_impl_files if svc_impl_files else svc_interface_files

        if not anchor_files:
            logger.warning("SVC Implementation 파일이 없습니다.")
            return all_batches

        # SVC에 섞여있던 VO 파일들을 repository에 추가
        svc_vo_files = [
            x
            for x in svc_files_raw
            if x.endswith("VO.java") or x.endswith("SVO.java") or x.endswith("DVO.java")
        ]
        repository_files.extend(svc_vo_files)

        # repository에서 VO 파일만 추출
        vo_files = [
            x
            for x in repository_files
            if x.endswith("VO.java") or x.endswith("SVO.java") or x.endswith("DVO.java")
        ]

        # dem_daq에서 DQM과 DEM 파일 분리
        dqm_files = [x for x in dem_daq_files if "/dqm/" in x or x.endswith("DQM.java")]
        dem_files = [x for x in dem_daq_files if "/dem/" in x or x.endswith("DEM.java")]

        logger.info(f"=== AnyframeContextGenerator Starting ===")

        if not anchor_files:
            logger.warning("SVC 앵커 파일이 없습니다.")
            return all_batches

        java_parser = JavaASTParser()

        # Base source path 추론 (BIZ fallback에서 사용)
        base_src_path = self._infer_base_src_path(layer_files)

        # 각 SVC별 파일 그룹 저장
        file_groups: Dict[str, List[str]] = {}
        context_file_groups: Dict[str, List[str]] = {}

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: 각 ServiceImpl 파일별로 관련 파일 그룹화
        #
        # CORRECT FLOW (시작점이 ServiceImpl):
        # 1. ServiceImpl 파일 (anchor) → 옵션으로 Interface 찾기
        # 2. ServiceImpl 파싱 → BIZ imports 찾기 → BIZ 파일 매칭 (layer_files에서)
        # 3. BIZ 파일 파싱 → DQM/DEM/VO imports 찾기 → 매칭 (layer_files에서)
        # 4. 관련 배치 생성
        # ═══════════════════════════════════════════════════════════════

        for svc_impl_file in anchor_files:
            impl_path = Path(svc_impl_file)
            impl_key = impl_path.stem

            file_group_paths: List[str] = []
            vo_group_paths: List[str] = []

            try:
                # ─────────────────────────────────────────────────────────
                # STEP 2-1: ServiceImpl (anchor) 시작, 옵션으로 Interface 추가
                # ─────────────────────────────────────────────────────────
                file_group_paths.append(svc_impl_file)

                # ServiceImpl에 매칭되는 Interface가 있으면 추가
                interface_file = impl_to_interface.get(svc_impl_file)
                if interface_file:
                    file_group_paths.append(interface_file)

                # ─────────────────────────────────────────────────────────
                # STEP 2-2: ServiceImpl 파일 파싱 → BIZ imports 찾기
                # ─────────────────────────────────────────────────────────
                tree, error = java_parser.parse_file(impl_path)

                if error:
                    logger.warning(f"ServiceImpl 파싱 실패: {svc_impl_file} - {error}")
                    file_groups[impl_key] = file_group_paths
                    context_file_groups[impl_key] = []
                    continue

                classes = java_parser.extract_class_info(tree, impl_path)
                if not classes:
                    logger.warning(f"ServiceImpl에서 클래스 정보 없음: {svc_impl_file}")
                    file_groups[impl_key] = file_group_paths
                    context_file_groups[impl_key] = []
                    continue

                impl_class = next(
                    (c for c in classes if c.access_modifier == "public"),
                    classes[0],
                )

                impl_imports = set(impl_class.imports)

                # ─────────────────────────────────────────────────────────
                # STEP 2-3: ServiceImpl imports에서 BIZ 파일 매칭
                #           타겟 DQM/DEM까지의 전체 BIZ 체인 찾기
                # ─────────────────────────────────────────────────────────
                matched_biz_files: List[str] = []
                all_biz_chains: List[List[str]] = []

                # Step 1: layer_files["biz"]에서 직접 매칭되는 BIZ
                for import_stmt in impl_imports:
                    matched = self._match_import_to_file_path(import_stmt, biz_files)
                    if matched and matched not in matched_biz_files:
                        # 이 BIZ가 타겟 DQM/DEM으로 이어지는지 확인
                        visited = set()
                        chain = self._find_biz_chain_to_target(
                            matched,
                            base_src_path,
                            biz_files,
                            dqm_files,
                            dem_files,
                            java_parser,
                            visited,
                            [],
                        )
                        if chain:
                            all_biz_chains.append(chain)
                            matched_biz_files.extend(
                                [b for b in chain if b not in matched_biz_files]
                            )

                # Step 2: layer_files에 없는 BIZ도 확인 (fallback)
                if base_src_path:
                    for import_stmt in impl_imports:
                        if (
                            "biz" not in import_stmt.lower()
                            and "BIZ" not in import_stmt
                        ):
                            continue

                        # 이미 layer_files에서 찾았으면 skip
                        if self._match_import_to_file_path(import_stmt, biz_files):
                            continue

                        # Import → 파일 경로 변환
                        biz_file_path = self._convert_import_to_file_path(
                            import_stmt, base_src_path
                        )
                        if not biz_file_path or biz_file_path in matched_biz_files:
                            continue

                        # 타겟까지의 체인 찾기
                        visited = set()
                        chain = self._find_biz_chain_to_target(
                            biz_file_path,
                            base_src_path,
                            biz_files,
                            dqm_files,
                            dem_files,
                            java_parser,
                            visited,
                            [],
                        )
                        if chain:
                            all_biz_chains.append(chain)
                            matched_biz_files.extend(
                                [b for b in chain if b not in matched_biz_files]
                            )

                fallback_biz_count = sum(
                    1
                    for chain in all_biz_chains
                    for biz in chain
                    if not self._match_import_to_file_path(Path(biz).stem, biz_files)
                )

                # ─────────────────────────────────────────────────────────
                # STEP 2-4: 찾은 BIZ 파일들에서 DQM/DEM 수집
                #           (재귀 없음 - 타겟 DQM/DEM 찾으면 stop했으므로)
                # ─────────────────────────────────────────────────────────
                all_imports_for_vo: set = set(impl_imports)
                matched_dqm_files: List[str] = []
                matched_dem_files: List[str] = []

                for biz_file in matched_biz_files:
                    try:
                        biz_tree, biz_error = java_parser.parse_file(Path(biz_file))
                        if biz_error:
                            continue

                        biz_classes = java_parser.extract_class_info(
                            biz_tree, Path(biz_file)
                        )
                        if not biz_classes:
                            continue

                        biz_class = next(
                            (c for c in biz_classes if c.access_modifier == "public"),
                            biz_classes[0],
                        )

                        biz_imports = set(biz_class.imports)
                        all_imports_for_vo.update(biz_imports)

                        # BIZ imports에서 타겟 DQM/DEM 수집
                        for import_stmt in biz_imports:
                            matched = self._match_import_to_file_path(
                                import_stmt, dqm_files
                            )
                            if matched and matched not in matched_dqm_files:
                                matched_dqm_files.append(matched)

                            matched = self._match_import_to_file_path(
                                import_stmt, dem_files
                            )
                            if matched and matched not in matched_dem_files:
                                matched_dem_files.append(matched)

                        # Same-package DQM/DEM
                        same_pkg_dqm = self._find_same_package_references(
                            biz_file, dqm_files
                        )
                        for dqm in same_pkg_dqm:
                            if dqm not in matched_dqm_files:
                                matched_dqm_files.append(dqm)

                        same_pkg_dem = self._find_same_package_references(
                            biz_file, dem_files
                        )
                        for dem in same_pkg_dem:
                            if dem not in matched_dem_files:
                                matched_dem_files.append(dem)

                    except Exception as e:
                        logger.debug(f"BIZ 처리 실패: {Path(biz_file).name} - {e}")

                file_group_paths.extend(matched_biz_files)
                file_group_paths.extend(matched_dqm_files)
                file_group_paths.extend(matched_dem_files)

                # ─────────────────────────────────────────────────────────
                # STEP 2-5: DQM/DEM imports 수집 (VO 선택용)
                #           재귀 없음 - 이미 타겟 DQM/DEM을 찾았으므로
                # ─────────────────────────────────────────────────────────
                for dqm_file in matched_dqm_files:
                    try:
                        dqm_tree, dqm_error = java_parser.parse_file(Path(dqm_file))
                        if not dqm_error:
                            dqm_classes = java_parser.extract_class_info(
                                dqm_tree, Path(dqm_file)
                            )
                            if dqm_classes:
                                dqm_class = next(
                                    (
                                        c
                                        for c in dqm_classes
                                        if c.access_modifier == "public"
                                    ),
                                    dqm_classes[0],
                                )
                                all_imports_for_vo.update(dqm_class.imports)
                    except Exception as e:
                        logger.debug(f"DQM 처리 실패: {Path(dqm_file).name} - {e}")

                for dem_file in matched_dem_files:
                    try:
                        dem_tree, dem_error = java_parser.parse_file(Path(dem_file))
                        if not dem_error:
                            dem_classes = java_parser.extract_class_info(
                                dem_tree, Path(dem_file)
                            )
                            if dem_classes:
                                dem_class = next(
                                    (
                                        c
                                        for c in dem_classes
                                        if c.access_modifier == "public"
                                    ),
                                    dem_classes[0],
                                )
                                all_imports_for_vo.update(dem_class.imports)
                    except Exception as e:
                        logger.debug(f"DEM 처리 실패: {Path(dem_file).name} - {e}")

                # ─────────────────────────────────────────────────────────
                # STEP 2-6: 모든 파일의 모든 imports에서 VO 파일 선택
                # ─────────────────────────────────────────────────────────
                vo_group_paths = self._select_vo_files_by_token_budget(
                    vo_files=vo_files,
                    all_imports=all_imports_for_vo,
                    max_tokens=self.MAX_VO_TOKENS,
                )

                # ═══════════════════════════════════════════════════════════
                # STREAMLINED SUMMARY LOG
                # ═══════════════════════════════════════════════════════════
                svc_count = 1 + (1 if interface_file else 0)
                logger.info(
                    f"✓ {impl_key}: "
                    f"SVC={svc_count}, "
                    f"BIZ={len(matched_biz_files)}"
                    f"{f' (fallback={fallback_biz_count})' if fallback_biz_count > 0 else ''}, "
                    f"DQM={len(matched_dqm_files)}, "
                    f"DEM={len(matched_dem_files)}, "
                    f"VO={len(vo_group_paths)}"
                )

            except Exception as e:
                logger.warning(f"ServiceImpl 파일 처리 실패: {svc_impl_file} - {e}")
                file_groups[impl_key] = file_group_paths
                context_file_groups[impl_key] = []
                continue

            # 그룹 저장
            file_groups[impl_key] = file_group_paths
            context_file_groups[impl_key] = vo_group_paths

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: 각 그룹별로 배치 생성
        # ═══════════════════════════════════════════════════════════════

        for impl_key, file_group_paths in file_groups.items():
            if len(file_group_paths) == 0:
                continue

            vo_files_for_group = context_file_groups.get(impl_key, [])

            batches = self.create_batches(
                file_paths=file_group_paths,  # 수정 대상: ServiceImpl + Interface + BIZ + DQM + DEM
                table_name=table_name,
                columns=columns,
                layer="",
                context_files=vo_files_for_group,  # Context only: 관련 VO들
            )
            all_batches.extend(batches)

        logger.info(f"=== Total Batches Created: {len(all_batches)} ===")
        return all_batches
