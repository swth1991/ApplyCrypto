"""
BNK Batch SQL Extractor

BNK 배치 프로그램의 *_SQL.xml 파일에서 SQL을 추출하는 구현 클래스입니다.

BatchBaseSQLExtractor와의 차이점:
    - XML 파일 패턴: *_SQL.xml (Base의 추상 메서드 구현)
    - BATVO 수집: batvo/ 디렉토리 + 같은 디렉토리의 *BATVO.java 모두 검색
"""

import logging
from pathlib import Path
from typing import List, override

from config.config_manager import Configuration
from models.source_file import SourceFile
from parser.xml_mapper_parser import XMLMapperParser

from .batch_base_sql_extractor import BatchBaseSQLExtractor


class BNKBatchSQLExtractor(BatchBaseSQLExtractor):
    """
    BNK 배치용 SQL Extractor 구현 클래스

    BatchBaseSQLExtractor를 상속하며,
    파일 필터링 패턴과 BATVO 수집 범위가 다릅니다.
    - 파일 필터: *_SQL.xml
    - BATVO 수집: batvo/ 하위 + 같은 디렉토리의 *BATVO.java
    """

    def __init__(
        self,
        config: Configuration,
        xml_parser: XMLMapperParser = None,
        java_parse_results: List[dict] = None,
        call_graph_builder=None,
    ):
        super().__init__(
            config=config,
            xml_parser=xml_parser,
            java_parse_results=java_parse_results,
            call_graph_builder=call_graph_builder,
        )
        self.logger = logging.getLogger(__name__)

    @override
    def filter_sql_files(self, source_files: List[SourceFile]) -> List[SourceFile]:
        """
        BNK 배치 관련 파일 필터링 (*_SQL.xml)

        CCS batch의 *BAT_SQL.xml보다 넓은 *_SQL.xml 패턴을 사용합니다.

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SourceFile]: 필터링된 파일 목록
        """
        filtered = []
        for f in source_files:
            if f.extension == ".xml":
                name_upper = f.filename.upper()
                if name_upper.endswith("_SQL.XML"):
                    filtered.append(f)
                    self.logger.debug(f"BNK 배치 SQL 파일 포함: {f.filename}")

        self.logger.info(f"BNK 배치 SQL 파일 필터링 완료: {len(filtered)}개 파일")
        return filtered

    @override
    def _find_batvo_files(self, bat_dir: Path) -> List[str]:
        """
        BATVO 파일 수집 - batvo/ 하위 AND 같은 디렉토리 모두 검색

        Base는 batvo/ 하위만 검색하지만,
        BNK batch는 같은 디렉토리의 *BATVO.java도 함께 수집합니다.

        Args:
            bat_dir: BAT 파일이 있는 디렉토리

        Returns:
            List[str]: BATVO 파일 경로 목록
        """
        # 1. 부모 클래스의 batvo/ 디렉토리 검색
        batvo_files = super()._find_batvo_files(bat_dir)

        # 2. 같은 디렉토리에서 *BATVO.java 패턴 추가 수집
        for java_file in bat_dir.glob("*.java"):
            if java_file.name.upper().endswith("BATVO.JAVA"):
                file_str = str(java_file)
                if file_str not in batvo_files:
                    batvo_files.append(file_str)
                    self.logger.debug(f"BNK BATVO 파일 수집 (같은 디렉토리): {java_file.name}")

        # 3. 소스 파일 캐시에서 같은 디렉토리의 BATVO 파일 추가 확인
        bat_dir_str = str(bat_dir).lower()
        for source_file in self.source_files_cache:
            if source_file.extension == ".java":
                file_path_str = str(source_file.path).lower()
                file_name_upper = source_file.path.name.upper()
                # 같은 디렉토리에 있는 BATVO 파일
                if (
                    bat_dir_str in file_path_str
                    and file_name_upper.endswith("BATVO.JAVA")
                ):
                    file_path = str(source_file.path)
                    if file_path not in batvo_files:
                        batvo_files.append(file_path)

        return batvo_files
