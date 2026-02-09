"""
MyBatis SQL Extractor

MyBatis XML Mapper 파일에서 SQL을 추출하는 구현 클래스입니다.
"""

import logging
from typing import List, override

from config.config_manager import Configuration
from models.source_file import SourceFile
from models.sql_extraction_output import SQLExtractionOutput
from models.sql_extraction_output import ExtractedSQLQuery
from parser.xml_mapper_parser import XMLMapperParser
from util.dynamic_sql_resolver import DynamicSQLResolver

from .mybatis_sql_extractor import MyBatisSQLExtractor 

class MyBatisDirectSQLExtractor(MyBatisSQLExtractor):
    """
    MyBatis Direct SQL Extractor 구현 클래스

    MyBatis XML Mapper 파일에서 SQL을 추출합니다.
    config.use_llm_parser가 True인 경우 LLMSQLExtractor를 사용합니다.
    """

    def __init__(
        self,
        config: Configuration,
        xml_parser: XMLMapperParser = None,
        java_parse_results: List[dict] = None,
        call_graph_builder = None,
    ):
        """
        MyBatisSQLExtractor 초기화

        Args:
            config: 설정 객체
            xml_parser: XML Mapper 파서
            java_parse_results: Java 파싱 결과 리스트 (사용하지 않지만 호환성을 위해 유지)
            call_graph_builder: CallGraphBuilder 인스턴스 (선택적)
        """
        super().__init__(config=config, xml_parser=xml_parser, java_parse_results=java_parse_results, call_graph_builder=call_graph_builder)
        self.logger = logging.getLogger(__name__)


    @override
    def extract_sqls(
        self, source_files: List[SourceFile]
    ) -> List[SQLExtractionOutput]:
        """
        MyBatis 전략: XML Mapper 파일에서 SQL 추출

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SQLExtractionOutput]: 추출 결과
        """

        results = []
        
        for xml_file in source_files:
            try:
                parse_result = self.xml_parser.parse_mapper_file(xml_file.path)
                if parse_result.get("error"):
                    continue

                # SQL 쿼리들을 strategy 중립적인 형식으로 변환
                sql_queries = []
                for query in parse_result.get("sql_queries", []):
                    # strategy_specific에 MyBatis 특정 정보 저장
                    # 제네릭 타입에서 내부 클래스 타입 추출
                    parameter_type = self._extract_generic_inner_type(query.get("parameter_type"))
                    result_type = self._extract_generic_inner_type(query.get("result_type"))
                    result_map = self._extract_generic_inner_type(query.get("result_map"))

                    strategy_specific = {
                        "namespace": query.get("namespace", ""),
                        "parameter_type": parameter_type,
                        "result_type": result_type,
                        "result_map": result_map,
                        # resultMap 내부 필드 매핑 (SELECT용)
                        "result_field_mappings": query.get("result_field_mappings", []),
                        # SQL 내 #{fieldName} 패턴 (INSERT/UPDATE용)
                        "parameter_field_mappings": query.get("parameter_field_mappings", []),
                        "xml_file_path": xml_file.path,
                    }

                    sql_query = query.get("sql", "")

                    resolver = DynamicSQLResolver()
                    resolved_sql = resolver.resolve_dynamic_sql(
                        xml_path=xml_file.path,
                        sql_id=query.get("id"),
                    ) or sql_query

                    sql_queries.append(
                        ExtractedSQLQuery(
                            id=query.get("id", ""),
                            query_type=query.get("query_type", "SELECT"),
                            sql=resolved_sql,
                            strategy_specific=strategy_specific,
                        )
                    )

                if sql_queries:
                    results.append(
                        SQLExtractionOutput(file=xml_file, sql_queries=sql_queries)
                    )

            except Exception as e:
                self.logger.warning(f"XML 파일 추출 실패: {xml_file.path} - {e}")

        return results
