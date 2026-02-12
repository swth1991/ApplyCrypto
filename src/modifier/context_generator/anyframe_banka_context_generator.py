"""
Anyframe Banka Context Generator

BNK 온라인 타입 전용 Context Generator입니다.

주요 기능:
1. generate(): call_stack 기반 파일 그룹핑
   - AnyframeContextGenerator(import-chasing)와 독립적으로 동작합니다.
   - BNK 프로젝트에서는 Spring DI/XML 주입으로 연결된 클래스의 import가 없어
     import-chasing이 작동하지 않으므로, call_stack 데이터를 직접 사용합니다.
   - access_files → SVC 식별 → call_stack 시작점 매칭 → 하위 BIZ 수집.

2. create_batches(): BIZ 메서드 레벨 토큰 계산
   - BIZ 파일은 call_stack 기반 메서드만으로 토큰을 계산하여 배치 분할 최적화.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from config.config_manager import Configuration
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from modifier.code_generator.base_code_generator import BaseCodeGenerator
from modifier.context_generator.base_context_generator import BaseContextGenerator
from parser.java_ast_parser import JavaASTParser

logger = logging.getLogger("applycrypto.anyframe_banka_context_generator")


class AnyframeBankaContextGenerator(BaseContextGenerator):
    """BNK 온라인 전용 Context Generator

    call_stack 데이터를 직접 사용하여 SVC→BIZ 그룹핑을 수행합니다.
    AnyframeContextGenerator(import-chasing)와 독립적으로 동작하며,
    access_files에서 SVC를 찾고 call_stack 시작점이 일치하는 BIZ를 수집합니다.
    """

    # VO 파일 최대 토큰 예산 (AnyframeContextGenerator와 동일)
    MAX_VO_TOKENS = 80000

    # 토큰 제한 사용 여부 (False로 설정하면 모든 VO 파일 포함)
    USE_TOKEN_LIMIT = True

    def __init__(self, config: Configuration, code_generator: BaseCodeGenerator):
        super().__init__(config, code_generator)
        self._java_parser = JavaASTParser()
        self._table_access_info: Optional[TableAccessInfo] = None

    # ========== generate 오버라이드 (call_stack 기반) ==========

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
        table_access_info: Optional[TableAccessInfo] = None,
        endpoint_method: Optional[str] = None,
    ) -> List[ModificationContext]:
        """call_stack 기반 파일 그룹핑으로 배치를 생성합니다.

        알고리즘:
        1. access_files에서 SVC 파일 식별
        2. 각 SVC 기준으로 모든 sql_queries 순회
        3. call_stack 시작이 현재 SVC와 같으면 하위 BIZ를 수집
        4. SVCImpl + SVC Interface + BIZ 파일 그룹 생성
        5. VO 파일 선택 (import 기반)
        6. 배치 생성

        table_access_info가 없으면 빈 리스트를 반환합니다 (banka는 항상 필요).
        """
        self._table_access_info = table_access_info

        if not table_access_info:
            logger.warning(
                "table_access_info가 없습니다. "
                "BNK 온라인 타입은 table_access_info가 필수입니다."
            )
            return []

        # ═══ STEP 1: 레이어별 파일 추출 (부모와 동일) ═══
        # classify_layer()가 "SVC"/"SVCImpl"을 반환하고 _find_upper_layer_files()에서
        # .lower()로 변환되므로 "svc"와 "svcimpl" 키가 별도로 존재합니다.
        # 두 키를 병합하여 SVC Interface + SVCImpl을 모두 포함합니다.
        svc_files_raw = layer_files.get("svc", []) + layer_files.get("svcimpl", [])
        biz_files_raw = layer_files.get("biz", [])
        repository_files = layer_files.get("Repository", [])
        dem_daq_files = layer_files.get("dem_daq", [])

        # BIZ stem 필터 (Util 제외, 대소문자 무시)
        biz_files = [f for f in biz_files_raw if Path(f).stem.upper().endswith("BIZ")]
        if len(biz_files) < len(biz_files_raw):
            excluded = [
                Path(f).name for f in biz_files_raw if not Path(f).stem.upper().endswith("BIZ")
            ]
            logger.info(
                f"BIZ stem 필터: {len(biz_files_raw)} → {len(biz_files)}개 "
                f"(제외: {', '.join(excluded[:5])}{'...' if len(excluded) > 5 else ''})"
            )

        # SVC 분류
        svc_files_all = [
            x
            for x in svc_files_raw
            if not (
                x.endswith("VO.java")
                or x.endswith("SVO.java")
                or x.endswith("DVO.java")
            )
        ]
        svc_impl_files = [x for x in svc_files_all if x.endswith("Impl.java")]
        svc_interface_files = [x for x in svc_files_all if not x.endswith("Impl.java")]

        # VO 파일
        svc_vo_files = [
            x
            for x in svc_files_raw
            if x.endswith("VO.java") or x.endswith("SVO.java") or x.endswith("DVO.java")
        ]
        all_repository = repository_files + svc_vo_files
        vo_files = [
            x
            for x in all_repository
            if x.endswith("VO.java") or x.endswith("SVO.java") or x.endswith("DVO.java")
        ]

        # DQM (VO import 수집용)
        dqm_files = [x for x in dem_daq_files if "/dqm/" in x or x.endswith("DQM.java")]

        # ═══ STEP 2: class_name → file_path 매핑 ═══
        impl_name_to_path = {Path(f).stem: f for f in svc_impl_files}
        interface_name_to_path = {Path(f).stem: f for f in svc_interface_files}
        biz_name_to_path = {Path(f).stem: f for f in biz_files}
        dqm_name_to_path = {Path(f).stem: f for f in dqm_files}

        # SVC 전체 (interface + impl) 매핑
        svc_name_to_path: Dict[str, str] = {}
        svc_name_to_path.update(interface_name_to_path)
        svc_name_to_path.update(impl_name_to_path)

        # ═══ STEP 3: access_files에서 SVC 파일 식별 ═══
        access_files = table_access_info.access_files
        svc_in_access: List[str] = []
        for af in access_files:
            stem = Path(af).stem
            if stem in svc_name_to_path:
                svc_in_access.append(stem)

        # SVCImpl과 SVC Interface 구분
        svc_impl_names = [s for s in svc_in_access if s in impl_name_to_path]
        svc_intf_names = [s for s in svc_in_access if s in interface_name_to_path]

        # anchor는 SVCImpl 기준 (없으면 SVC Interface)
        anchor_names = svc_impl_names if svc_impl_names else svc_intf_names

        if not anchor_names:
            logger.warning(
                "access_files에서 SVC 파일을 찾을 수 없습니다. "
                "call_stack 기반 그룹핑을 수행할 수 없습니다."
            )
            return []

        logger.info(f"call_stack 기반 그룹핑 시작: anchor SVC {len(anchor_names)}개")

        # ═══ STEP 4: 각 SVC 기준으로 call_stack 순회 → BIZ 수집 ═══
        impl_to_biz_names: Dict[str, Set[str]] = {}
        impl_to_svc_names: Dict[str, Set[str]] = {}
        impl_to_dqm_names: Dict[str, Set[str]] = {}

        for svc_name in anchor_names:
            impl_to_biz_names.setdefault(svc_name, set())
            impl_to_svc_names.setdefault(svc_name, set())
            impl_to_dqm_names.setdefault(svc_name, set())

            for sq in table_access_info.sql_queries:
                for cs in sq.get("call_stacks", []):
                    if not isinstance(cs, list) or not cs:
                        continue

                    # call_stack 시작이 현재 SVC와 같은지 확인 (첫 2개 entry)
                    cs_starts_with_this_svc = False
                    for entry in cs[:2]:
                        if not isinstance(entry, str) or "." not in entry:
                            continue
                        entry_class = entry.split(".")[0]
                        if entry_class == svc_name:
                            cs_starts_with_this_svc = True
                            break
                        # SVCImpl ↔ SVC Interface 페어링 체크
                        if (
                            entry_class in impl_name_to_path
                            or entry_class in interface_name_to_path
                        ):
                            pair_candidates = self._get_svc_pair_candidates(entry_class)
                            if svc_name in pair_candidates:
                                cs_starts_with_this_svc = True
                                break

                    if not cs_starts_with_this_svc:
                        continue

                    # 이 call_stack의 모든 entry에서 BIZ/SVC/DQM 분류
                    for entry in cs:
                        if not isinstance(entry, str) or "." not in entry:
                            continue
                        class_name = entry.split(".")[0]

                        if class_name in biz_name_to_path:
                            impl_to_biz_names[svc_name].add(class_name)
                        elif (
                            class_name in interface_name_to_path
                            and class_name != svc_name
                        ):
                            impl_to_svc_names[svc_name].add(class_name)
                        elif (
                            class_name in impl_name_to_path
                            and class_name != svc_name
                        ):
                            impl_to_svc_names[svc_name].add(class_name)
                        elif class_name in dqm_name_to_path:
                            impl_to_dqm_names[svc_name].add(class_name)

        # ═══ STEP 5: 파일 그룹 생성 ═══
        java_parser = JavaASTParser()
        file_groups: Dict[str, List[str]] = {}
        context_file_groups: Dict[str, List[str]] = {}

        for svc_name in anchor_names:
            biz_names = impl_to_biz_names.get(svc_name, set())
            svc_path = svc_name_to_path.get(svc_name)
            if not svc_path:
                continue

            file_group_paths: List[str] = [svc_path]

            # SVC Interface/Impl 페어 추가 (call_stack에서 찾은 것)
            svc_names_from_cs = impl_to_svc_names.get(svc_name, set())
            for paired_name in svc_names_from_cs:
                paired_path = svc_name_to_path.get(paired_name)
                if paired_path and paired_path not in file_group_paths:
                    file_group_paths.append(paired_path)

            # BIZ 파일 추가 (call_stack에서 직접 추출)
            matched_biz_files: List[str] = []
            for biz_name in sorted(biz_names):
                biz_path = biz_name_to_path.get(biz_name)
                if biz_path:
                    matched_biz_files.append(biz_path)
                else:
                    logger.warning(
                        f"call_stack BIZ '{biz_name}' not found in layer_files"
                    )
            file_group_paths.extend(matched_biz_files)

            # DQM/DEM 파일 제외 (SQL 쿼리 접근 클래스이므로 수정 대상 아님)
            before_filter = len(file_group_paths)
            file_group_paths = [
                fp
                for fp in file_group_paths
                if not (
                    Path(fp).stem.endswith("DQM")
                    or Path(fp).stem.endswith("DEM")
                    or "/dqm/" in fp
                    or "/dem/" in fp
                )
            ]
            if len(file_group_paths) < before_filter:
                logger.info(
                    f"DQM/DEM 필터: {before_filter} → {len(file_group_paths)}개 "
                    f"(수정 대상에서 제외)"
                )

            # VO 선택: 그룹 내 파일 + DQM의 imports 기반
            all_imports_for_vo: set = set()
            for fp in file_group_paths:
                try:
                    tree, error = java_parser.parse_file(Path(fp))
                    if not error:
                        classes = java_parser.extract_class_info(tree, Path(fp))
                        if classes:
                            cls = next(
                                (c for c in classes if c.access_modifier == "public"),
                                classes[0],
                            )
                            all_imports_for_vo.update(cls.imports)
                except Exception:
                    pass

            # DQM imports도 VO 선택에 포함
            for dqm_name in impl_to_dqm_names.get(svc_name, set()):
                dqm_path = dqm_name_to_path.get(dqm_name)
                if dqm_path:
                    try:
                        tree, error = java_parser.parse_file(Path(dqm_path))
                        if not error:
                            classes = java_parser.extract_class_info(
                                tree, Path(dqm_path)
                            )
                            if classes:
                                cls = next(
                                    (
                                        c
                                        for c in classes
                                        if c.access_modifier == "public"
                                    ),
                                    classes[0],
                                )
                                all_imports_for_vo.update(cls.imports)
                    except Exception:
                        pass

            vo_group_paths = self._select_vo_files_by_token_budget(
                vo_files=vo_files,
                all_imports=all_imports_for_vo,
                max_tokens=self.MAX_VO_TOKENS,
            )

            logger.info(
                f"✓ {svc_name}: SVC={len([p for p in file_group_paths if p not in matched_biz_files])}, "
                f"BIZ={len(matched_biz_files)} ({', '.join(sorted(biz_names))}), "
                f"VO={len(vo_group_paths)}"
            )

            file_groups[svc_name] = file_group_paths
            context_file_groups[svc_name] = vo_group_paths

        # ═══ STEP 6: 배치 생성 ═══
        all_batches: List[ModificationContext] = []
        for svc_name, file_group_paths in file_groups.items():
            if not file_group_paths:
                continue
            vo_files_for_group = context_file_groups.get(svc_name, [])
            batches = self.create_batches(
                file_paths=file_group_paths,
                table_name=table_name,
                columns=columns,
                layer="",
                context_files=vo_files_for_group,
            )
            all_batches.extend(batches)

        logger.info(f"=== Total Batches Created: {len(all_batches)} ===")
        return all_batches

    def _get_svc_pair_candidates(self, class_name: str) -> Set[str]:
        """SVCImpl ↔ SVC Interface 페어링 후보를 반환합니다.

        예: IAIBslDoc040570SVCImpl → {IAIBslDoc040570SVC, IIAIBslDoc040570SVC}
            IAIBslDoc040570SVC → {IAIBslDoc040570SVCImpl}
        """
        candidates: Set[str] = set()
        if class_name.endswith("Impl"):
            base = class_name[:-4]  # Impl 제거
            candidates.add(base)
            candidates.add("I" + base)
        else:
            candidates.add(class_name + "Impl")
            # I 접두사 제거 시도
            if class_name.startswith("I") and len(class_name) > 1:
                candidates.add(class_name[1:] + "Impl")
        return candidates

    # ========== create_batches 오버라이드 ==========

    def create_batches(
        self,
        file_paths: List[str],
        table_name: str,
        columns: List[Dict],
        layer: str = "",
        context_files: List[str] = None,
    ) -> List[ModificationContext]:
        """BIZ 파일은 메서드 레벨 토큰으로 계산하여 배치 분할

        BaseContextGenerator.create_batches()와 동일한 배치 분할 로직이지만,
        BIZ 파일의 토큰을 전체 파일 대신 call_stack 참조 메서드만으로 계산합니다.

        table_access_info가 없으면 BaseContextGenerator의 전체 파일 기반 로직으로 fallback.
        """
        if not self._table_access_info:
            return super().create_batches(
                file_paths, table_name, columns, layer, context_files
            )

        if context_files is None:
            context_files = []
        if not file_paths:
            return []

        # call_stacks 추출
        raw_call_stacks = self._extract_raw_call_stacks(
            file_paths, self._table_access_info
        )

        batches: List[ModificationContext] = []
        current_paths: List[str] = []

        # 기본 정보 준비 (부모와 동일)
        from models.code_generator import CodeGeneratorInput

        table_info = {
            "table_name": table_name,
            "columns": columns,
        }
        formatted_table_info = json.dumps(table_info, indent=2, ensure_ascii=False)
        max_tokens = self._config.max_tokens_per_batch

        input_empty_data = CodeGeneratorInput(
            file_paths=[], table_info=formatted_table_info, layer_name=layer
        )

        empty_prompt = self._code_generator.create_prompt(input_empty_data)
        empty_num_tokens = self._code_generator.calculate_token_size(empty_prompt)
        separator_tokens = self._code_generator.calculate_token_size("\n\n")

        current_batch_tokens = empty_num_tokens

        for file_path in file_paths:
            try:
                path_obj = Path(file_path)
                if not path_obj.exists():
                    logger.warning(f"File not found during batch creation: {file_path}")
                    continue

                # ━━━ 핵심 차이: BIZ 파일은 메서드만으로 토큰 계산 ━━━
                if self._is_biz_file(file_path):
                    content = self._get_biz_method_content(file_path, raw_call_stacks)
                else:
                    with open(path_obj, "r", encoding="utf-8") as f:
                        content = f.read()

            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                continue

            snippet_formatted = f"=== File Path (Absolute): {file_path} ===\n{content}"
            snippet_tokens = self._code_generator.calculate_token_size(
                snippet_formatted
            )

            tokens_to_add = snippet_tokens
            if current_paths:
                tokens_to_add += separator_tokens

            if current_paths and (current_batch_tokens + tokens_to_add) > max_tokens:
                batches.append(
                    ModificationContext(
                        file_paths=current_paths,
                        table_name=table_name,
                        columns=columns,
                        file_count=len(current_paths),
                        layer=layer,
                        context_files=context_files,
                    )
                )
                current_paths = [file_path]
                current_batch_tokens = empty_num_tokens + snippet_tokens
            else:
                current_paths.append(file_path)
                current_batch_tokens += tokens_to_add

        if current_paths:
            batches.append(
                ModificationContext(
                    file_paths=current_paths,
                    table_name=table_name,
                    columns=columns,
                    file_count=len(current_paths),
                    layer=layer,
                    context_files=context_files,
                )
            )

        logger.info(
            f"Split {len(file_paths)} files into {len(batches)} batches "
            f"(BIZ method-level token estimation)."
        )
        return batches

    # ========== BIZ 메서드 추출 헬퍼 ==========

    def _is_biz_file(self, file_path: str) -> bool:
        """BIZ 파일 여부 판별 — stem이 'BIZ'로 끝나는 파일만 (대소문자 무시)

        Util 파일(BIZUtil, StringUtil 등)은 제외합니다.
        """
        return Path(file_path).stem.upper().endswith("BIZ")

    def _extract_raw_call_stacks(
        self,
        file_paths: List[str],
        table_access_info: TableAccessInfo,
    ) -> List[List[str]]:
        """call_stacks를 List[List[str]]로 반환합니다.

        base_code_generator._get_callstacks_from_table_access_info()와
        동일한 필터링 로직이지만, JSON 문자열 대신 원본 리스트를 반환합니다.
        """
        call_stacks_list: List[List[str]] = []
        file_class_names = [Path(fp).stem for fp in file_paths]

        for sql_query in table_access_info.sql_queries:
            call_stacks = sql_query.get("call_stacks", [])
            if not call_stacks:
                continue

            for call_stack in call_stacks:
                if not isinstance(call_stack, list) or not call_stack:
                    continue

                first_method = call_stack[0]
                if not isinstance(first_method, str):
                    continue

                if "." in first_method:
                    method_class_name = first_method.split(".")[0]
                else:
                    method_class_name = first_method

                if method_class_name in file_class_names:
                    if call_stack not in call_stacks_list:
                        call_stacks_list.append(call_stack)

        return call_stacks_list

    def _get_target_methods_for_file(
        self,
        file_path: str,
        raw_call_stacks: List[List[str]],
    ) -> Set[str]:
        """call_stacks에서 특정 파일 클래스에 해당하는 메서드명을 수집합니다."""
        class_name = Path(file_path).stem
        target_methods: Set[str] = set()

        for call_stack in raw_call_stacks:
            for method_sig in call_stack:
                if "." in method_sig:
                    cls, method = method_sig.split(".", 1)
                    if cls == class_name:
                        target_methods.add(method)

        return target_methods

    def _get_biz_method_content(
        self,
        file_path: str,
        raw_call_stacks: List[List[str]],
    ) -> str:
        """BIZ 파일에서 call_stack 참조 메서드만 추출하여 텍스트 반환합니다.

        토큰 계산용으로 순수 메서드 코드만 반환합니다.
        매칭 메서드 없으면 전체 파일 내용을 반환합니다 (fallback).
        """
        target_methods = self._get_target_methods_for_file(file_path, raw_call_stacks)

        if not target_methods:
            logger.debug(
                f"BIZ 파일에 call_stack 메서드 없음, 전체 포함: {Path(file_path).name}"
            )
            return self._read_full_file(file_path)

        # JavaASTParser로 메서드 정보 획득
        tree, error = self._java_parser.parse_file(Path(file_path))
        if error:
            logger.warning(
                f"BIZ 파일 파싱 실패, 전체 포함: {Path(file_path).name} - {error}"
            )
            return self._read_full_file(file_path)

        classes = self._java_parser.extract_class_info(tree, Path(file_path))

        # 매칭 메서드의 라인 범위 수집
        method_ranges: List[tuple] = []
        for cls_info in classes:
            for method in cls_info.methods:
                if method.name in target_methods:
                    method_ranges.append(
                        (method.name, method.line_number, method.end_line_number)
                    )

        if not method_ranges:
            logger.debug(
                f"BIZ 파일에서 매칭 메서드 없음, 전체 포함: {Path(file_path).name}"
            )
            return self._read_full_file(file_path)

        # 파일에서 해당 라인만 추출
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
        except Exception as e:
            logger.warning(f"BIZ 파일 읽기 실패: {file_path} - {e}")
            return ""

        extracted_parts: List[str] = []
        for method_name, start_line, end_line in sorted(
            method_ranges, key=lambda x: x[1]
        ):
            lines = all_lines[start_line - 1 : end_line]
            extracted_parts.append("".join(lines))

        matched_names = [r[0] for r in method_ranges]
        logger.info(
            f"BIZ 토큰 추정 (메서드 레벨): {Path(file_path).name} -> "
            f"{len(method_ranges)}개 메서드 ({', '.join(matched_names)})"
        )

        return "\n\n".join(extracted_parts)

    def _read_full_file(self, file_path: str) -> str:
        """단일 파일의 전체 내용을 읽습니다."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"파일 읽기 실패: {file_path} - {e}")
            return ""

    # ========== VO 선택 관련 메서드 (AnyframeContextGenerator에서 복사) ==========

    def _calculate_token_size(self, text: str) -> int:
        """텍스트의 토큰 크기를 계산합니다."""
        # try:
        #     import tiktoken

        #     encoder = tiktoken.encoding_for_model("gpt-4")
        #     return len(encoder.encode(text))
        # except Exception:
        return len(text) // 4

    def _match_import_to_file_path(
        self, import_statement: str, target_files: List[str]
    ) -> Optional[str]:
        """
        import 문과 일치하는 파일을 target_files에서 찾습니다.

        Args:
            import_statement: Java import 문 (예: "sli.gps.bc.biz.UserBIZ")
            target_files: 매칭 대상 파일 목록

        Returns:
            매칭되는 파일 경로, 없으면 None
        """
        expected_path_parts = import_statement.split(".")
        expected_class_name = expected_path_parts[-1]

        for file_path in target_files:
            file_path_obj = Path(file_path)

            if file_path_obj.stem != expected_class_name:
                continue

            normalized_path = str(file_path_obj).replace("\\", "/")
            file_parts = normalized_path.split("/")

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
                logger.debug(
                    f"    ✓ Matched: {import_statement} -> {file_path_obj.name}"
                )
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

        Args:
            vo_files: 전체 VO 파일 목록
            all_imports: 모든 레이어의 import 문
            max_tokens: 최대 토큰 예산

        Returns:
            선택된 VO 파일 목록
        """
        selected_files: List[str] = []
        current_tokens = 0

        if not self.USE_TOKEN_LIMIT:
            logger.info("VO 선택 (토큰 제한 없음 - 파일 읽기 생략)")
            for imp in all_imports:
                matched = self._match_import_to_file_path(imp, vo_files)
                if matched and matched not in selected_files:
                    selected_files.append(matched)
            logger.info(f"VO 파일 선택 완료: {len(selected_files)}개")
            return selected_files

        logger.info("VO 선택 (토큰 제한 모드 - 파일 읽기 중...)")
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
                        logger.debug(
                            f"VO 선택: {Path(matched).name} "
                            f"({file_tokens:,} tokens, 누적: {current_tokens:,})"
                        )
                    else:
                        logger.info(
                            f"VO 토큰 예산 초과로 제외: {Path(matched).name} "
                            f"({file_tokens:,} tokens, 누적: {current_tokens:,})"
                        )
                        break
                except Exception as e:
                    logger.warning(f"VO 파일 읽기 실패: {matched} - {e}")

        logger.info(
            f"VO 파일 선택 완료: {len(selected_files)}개, "
            f"총 {current_tokens:,} tokens (예산: {max_tokens:,})"
        )
        return selected_files
