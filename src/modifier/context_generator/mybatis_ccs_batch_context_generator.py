"""
MybatisCCS Batch Context Generator

CCS 배치 프로그램용 Context Generator입니다.
BAT.java 파일을 수정 대상으로, BATVO.java 파일과 XXX_SQL.xml을 context로 포함합니다.

특징:
    - 수정 대상 (file_paths): BAT.java
    - 참조용 context (context_files): BATVO.java (import 기반 필터링) + XXX_SQL.xml
    - 레이어: bat, batvo
    - BAT.java의 import문을 파싱하여 실제 사용하는 BATVO만 포함
    - BAT 파일명 기준으로 대응하는 XML 파일 자동 매칭
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from config.config_manager import Configuration
from models.modification_context import ModificationContext
from parser.java_ast_parser import JavaASTParser

from .base_context_generator import BaseContextGenerator

logger = logging.getLogger("applycrypto.context_generator")


class MybatisCCSBatchContextGenerator(BaseContextGenerator):
    """
    CCS 배치 프로그램용 Context Generator

    BAT.java 파일을 수정 대상으로 하고,
    BATVO.java 파일 (import 기반 필터링)과 XXX_SQL.xml을 참조용 context로 포함합니다.

    ThreeStep 코드 생성을 위해:
    - Phase 1: BAT.java + BATVO들 + XML을 모두 LLM에 전달하여 데이터 흐름 분석
    - Phase 2: BAT.java + Phase 1 결과로 수정 지침 생성
    - Phase 3: BAT.java만 수정
    """

    # CCS 배치 레이어명 매핑 (소문자로 통일)
    LAYER_NAME_MAPPING = {
        "bat": "bat",
        "batvo": "batvo",
    }

    def __init__(self, config: Configuration, code_generator):
        """
        MybatisCCSBatchContextGenerator 초기화

        Args:
            config: 설정 객체
            code_generator: 코드 생성기 (토큰 계산용)
        """
        super().__init__(config, code_generator)
        self._java_parser = JavaASTParser()

    def _extract_imports_from_bat(self, bat_file_path: str) -> Set[str]:
        """
        BAT.java 파일에서 import 문을 추출합니다.

        Args:
            bat_file_path: BAT.java 파일 경로

        Returns:
            Set[str]: import 문 집합 (예: {"sli.ccs.cr.cmpgnmng.bat.batvo.XXXRegBATVO"})
        """
        try:
            path_obj = Path(bat_file_path)
            tree, error = self._java_parser.parse_file(path_obj)
            if error:
                logger.warning(f"BAT 파일 파싱 실패: {bat_file_path} - {error}")
                return set()

            classes = self._java_parser.extract_class_info(tree, path_obj)
            if not classes:
                logger.warning(f"BAT 파일에서 클래스 정보를 추출할 수 없습니다: {bat_file_path}")
                return set()

            # public 클래스 또는 첫 번째 클래스의 imports 반환
            bat_class = next(
                (c for c in classes if c.access_modifier == "public"), classes[0]
            )
            imports = set(bat_class.imports)
            logger.debug(f"BAT 파일 '{Path(bat_file_path).name}'에서 {len(imports)}개 import 추출")
            return imports

        except Exception as e:
            logger.warning(f"Import 추출 실패: {bat_file_path} - {e}")
            return set()

    def _filter_batvo_by_imports(
        self, bat_imports: Set[str], all_batvo_files: List[str]
    ) -> List[str]:
        """
        BAT.java의 import에 실제 포함된 BATVO 파일만 필터링합니다.

        매칭 전략:
        1. import의 마지막 클래스명과 BATVO 파일명 비교
        2. 대소문자 무시 매칭

        Args:
            bat_imports: BAT 파일의 import 문 집합
            all_batvo_files: batvo/ 디렉토리의 모든 파일

        Returns:
            List[str]: 실제 사용되는 BATVO 파일 경로 목록
        """
        if not bat_imports:
            logger.info("Import가 없어 모든 BATVO 파일을 포함합니다.")
            return all_batvo_files

        # import에서 클래스명만 추출 (마지막 부분)
        import_class_names = {imp.split(".")[-1].lower() for imp in bat_imports}

        filtered = []
        for batvo_file in all_batvo_files:
            batvo_name = Path(batvo_file).stem.lower()  # 확장자 제외
            if batvo_name in import_class_names:
                filtered.append(batvo_file)

        if not filtered:
            logger.warning(
                f"import 기반 BATVO 필터링 결과가 없습니다. "
                f"모든 BATVO ({len(all_batvo_files)}개) 포함합니다."
            )
            return all_batvo_files

        logger.info(f"BATVO 필터링: {len(all_batvo_files)} -> {len(filtered)}")
        return filtered

    def _find_xml_file(self, bat_file_path: str) -> Optional[str]:
        """
        BAT.java에 대응하는 XML 파일을 찾습니다.

        파일명 컨벤션: XXXRegBAT.java -> XXXRegBAT_SQL.xml

        Args:
            bat_file_path: BAT.java 파일 경로

        Returns:
            Optional[str]: XML 파일 경로, 없으면 None
        """
        bat_path = Path(bat_file_path)
        bat_name = bat_path.stem  # 예: "XXXRegBAT"
        xml_name = f"{bat_name}_SQL.xml"

        # 1. 같은 디렉토리에서 찾기
        xml_path = bat_path.parent / xml_name
        if xml_path.exists():
            logger.debug(f"XML 파일 발견 (같은 디렉토리): {xml_path}")
            return str(xml_path)

        # 2. 상위 디렉토리에서 찾기
        parent_xml_path = bat_path.parent.parent / xml_name
        if parent_xml_path.exists():
            logger.debug(f"XML 파일 발견 (상위 디렉토리): {parent_xml_path}")
            return str(parent_xml_path)

        # 3. bat/ 디렉토리 바깥에서 찾기 (xml/ 디렉토리가 별도로 있는 경우)
        # 예: bat/XXXRegBAT.java -> xml/XXXRegBAT_SQL.xml
        if bat_path.parent.name == "bat":
            sibling_xml_dir = bat_path.parent.parent / "xml"
            if sibling_xml_dir.exists():
                sibling_xml_path = sibling_xml_dir / xml_name
                if sibling_xml_path.exists():
                    logger.debug(f"XML 파일 발견 (xml 디렉토리): {sibling_xml_path}")
                    return str(sibling_xml_path)

        logger.warning(f"XML 파일을 찾을 수 없습니다: {xml_name} (BAT: {bat_file_path})")
        return None

    def _normalize_layer_files(
        self, layer_files: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        레이어명을 소문자로 정규화합니다.

        Args:
            layer_files: 레이어별 파일 경로 딕셔너리

        Returns:
            Dict[str, List[str]]: 정규화된 레이어 파일 딕셔너리
        """
        normalized: Dict[str, List[str]] = {}

        for layer_name, files in layer_files.items():
            normalized_name = self.LAYER_NAME_MAPPING.get(
                layer_name.lower(), layer_name.lower()
            )
            if normalized_name not in normalized:
                normalized[normalized_name] = []
            for f in files:
                if f not in normalized[normalized_name]:
                    normalized[normalized_name].append(f)

        logger.debug(
            f"레이어 정규화: {list(layer_files.keys())} -> {list(normalized.keys())}"
        )
        return normalized

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
    ) -> List[ModificationContext]:
        """
        CCS 배치용 context 생성

        수정 대상 (file_paths): BAT.java
        참조용 context (context_files): BATVO.java (import 기반 필터링) + XXX_SQL.xml

        각 BAT 파일에 대해:
        1. import 문을 파싱하여 실제 사용하는 BATVO만 필터링
        2. BAT 파일명 기준으로 대응하는 XML 파일 찾기
        3. context_files = filtered_batvo + xml_file

        Args:
            layer_files: 레이어별 파일 경로 딕셔너리 (bat, batvo)
            table_name: 테이블명
            columns: 컬럼 목록

        Returns:
            List[ModificationContext]: 생성된 context 목록
        """
        normalized = self._normalize_layer_files(layer_files)

        logger.info(
            f"MybatisCCSBatchContextGenerator: 레이어 정규화 완료 "
            f"({list(layer_files.keys())} -> {list(normalized.keys())})"
        )

        all_batches: List[ModificationContext] = []

        # BAT 파일 (수정 대상)
        bat_files = normalized.get("bat", [])

        # BATVO 파일 (context용 - 필터링 전)
        batvo_files = normalized.get("batvo", [])

        if not bat_files:
            logger.info("BAT Layer 파일이 없습니다.")
            return all_batches

        logger.info(
            f"CCS 배치 context 생성 시작: "
            f"{len(bat_files)}개 BAT 파일, "
            f"{len(batvo_files)}개 BATVO 후보"
        )

        # 각 BAT 파일에 대해 batch 생성
        for bat_file in bat_files:
            bat_name = Path(bat_file).name

            # 1. BAT 파일의 import 파싱
            bat_imports = self._extract_imports_from_bat(bat_file)

            # 2. import 기반 BATVO 필터링
            filtered_batvo = self._filter_batvo_by_imports(bat_imports, batvo_files)

            # 3. 대응 XML 파일 찾기
            xml_file = self._find_xml_file(bat_file)

            # 4. context_files = filtered_batvo + xml_file
            context_files = list(filtered_batvo)
            if xml_file:
                context_files.append(xml_file)

            logger.info(
                f"BAT 파일 '{bat_name}': "
                f"BATVO {len(filtered_batvo)}개, "
                f"XML {'있음' if xml_file else '없음'} "
                f"(총 context: {len(context_files)}개)"
            )

            # 5. batch 생성
            batches = self.create_batches(
                file_paths=[bat_file],
                table_name=table_name,
                columns=columns,
                layer="bat",
                context_files=context_files,
            )
            all_batches.extend(batches)

        logger.info(f"CCS 배치 context 생성 완료: 총 {len(all_batches)}개 batch")
        return all_batches
