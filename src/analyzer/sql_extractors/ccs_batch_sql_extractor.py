"""
CCS Batch SQL Extractor

CCS 배치 프로그램의 *BAT_SQL.xml 파일에서 SQL을 추출하는 구현 클래스입니다.

특징:
    - XML 파일 패턴: *BAT_SQL.xml
    - 그 외 공통 배치 로직은 BatchBaseSQLExtractor에서 상속
"""

import logging
from typing import List, override

from config.config_manager import Configuration
from models.source_file import SourceFile
from parser.xml_mapper_parser import XMLMapperParser

from .batch_base_sql_extractor import BatchBaseSQLExtractor


class CCSBatchSQLExtractor(BatchBaseSQLExtractor):
    """
    CCS 배치용 SQL Extractor 구현 클래스

    BatchBaseSQLExtractor를 상속하며,
    CCS 배치 전용 *BAT_SQL.xml 파일 필터링 패턴을 구현합니다.
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
        CCS 배치 관련 파일 필터링 (*BAT_SQL.xml)

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SourceFile]: 필터링된 파일 목록
        """
        filtered = []
        for f in source_files:
            if f.extension == ".xml":
                name_upper = f.filename.upper()
                # *BAT_SQL.xml 패턴 필터링
                if name_upper.endswith("BAT_SQL.XML"):
                    filtered.append(f)
                    self.logger.debug(f"CCS 배치 SQL 파일 포함: {f.filename}")

        self.logger.info(f"CCS 배치 SQL 파일 필터링 완료: {len(filtered)}개 파일")
        return filtered
