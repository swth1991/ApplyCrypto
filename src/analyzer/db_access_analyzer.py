"""
DB Access Analyzer 모듈

설정 파일의 테이블 및 칼럼 정보와 XML/Java 파일에서 추출한 SQL 쿼리를 비교하여,
특정 테이블에 접근하는 파일을 필터링하고 태그를 부여하는 DB Access Analyzer를 구현합니다.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from collections import defaultdict

from ..models.table_access_info import TableAccessInfo
from ..models.source_file import SourceFile
from ..parser.xml_mapper_parser import XMLMapperParser
from ..parser.java_ast_parser import JavaASTParser
from ..parser.call_graph_builder import CallGraphBuilder
from ..config.config_manager import ConfigurationManager
from .sql_parsing_strategy import SQLParsingStrategy, create_strategy


class DBAccessAnalyzer:
    """
    DB Access Analyzer 클래스
    
    XML Mapper Parser와 Java AST Parser 결과를 통합하여
    테이블 접근 파일을 식별하고 태그를 부여합니다.
    """
    
    # 레이어 분류 패턴
    LAYER_PATTERNS = {
        "Mapper": [r".*Mapper\.xml$", r".*\.xml$"],
        "DTO": [r".*DTO\.java$", r".*Dto\.java$", r".*dto\.java$"],
        "DAO": [r".*DAO\.java$", r".*Dao\.java$", r".*dao\.java$"],
        "Service": [r".*Service\.java$", r".*service\.java$"],
        "Controller": [r".*Controller\.java$", r".*controller\.java$"]
    }
    
    def __init__(
        self,
        config_manager: ConfigurationManager,
        xml_parser: Optional[XMLMapperParser] = None,
        java_parser: Optional[JavaASTParser] = None,
        call_graph_builder: Optional[CallGraphBuilder] = None
    ):
        """
        DBAccessAnalyzer 초기화
        
        Args:
            config_manager: 설정 매니저
            xml_parser: XML Mapper 파서 (선택적)
            java_parser: Java AST 파서 (선택적)
            call_graph_builder: Call Graph Builder (선택적)
        """
        self.config_manager = config_manager
        self.xml_parser = xml_parser or XMLMapperParser()
        self.java_parser = java_parser or JavaASTParser()
        self.call_graph_builder = call_graph_builder
        self.logger = logging.getLogger(__name__)
        
        # SQL 파싱 전략 생성
        sql_wrapping_type = config_manager.get("sql_wrapping_type", "mybatis")
        if not sql_wrapping_type:
            sql_wrapping_type = config_manager.sql_wrapping_type
        self.sql_strategy = create_strategy(sql_wrapping_type)
        
        # 설정에서 테이블 정보 가져오기
        self.access_tables = config_manager.get("access_tables", [])
        if not self.access_tables:
            self.access_tables = config_manager.access_tables
        self.table_column_map: Dict[str, Set[str]] = {}
        for table_info in self.access_tables:
            table_name = table_info.get("table_name", "").upper()
            columns = {col.upper() for col in table_info.get("columns", [])}
            self.table_column_map[table_name] = columns
    
    def analyze(
        self,
        source_files: List[SourceFile]
    ) -> List[TableAccessInfo]:
        """
        소스 파일들을 분석하여 테이블 접근 정보 추출
        
        Args:
            source_files: 분석할 소스 파일 목록
            
        Returns:
            List[TableAccessInfo]: 테이블 접근 정보 목록
        """
        # 파일-테이블 매핑 생성
        file_table_map = self._identify_table_access_files(source_files)
        
        # 파일 태그 부여
        tagged_files = self._assign_file_tags(source_files, file_table_map)
        
        # 레이어별 파일 분류
        layer_files = self._classify_files_by_layer(tagged_files)
        
        # 칼럼 레벨 분석
        table_access_info_list = self._analyze_column_level(file_table_map, layer_files)
        
        # 의존성 추적
        if self.call_graph_builder:
            self._track_dependencies(table_access_info_list, layer_files)
        
        return table_access_info_list
    
    def _identify_table_access_files(
        self,
        source_files: List[SourceFile]
    ) -> Dict[str, Set[str]]:
        """
        XML Mapper Parser와 Java AST Parser 결과를 통합하여 테이블 접근 파일 식별
        
        Args:
            source_files: 소스 파일 목록
            
        Returns:
            Dict[str, Set[str]]: 테이블명 -> 파일 경로 집합 매핑
        """
        file_table_map: Dict[str, Set[str]] = defaultdict(set)
        
        # Java 파일을 클래스명으로 매핑 (클래스 선언 파일 찾기용)
        class_to_files: Dict[str, Set[str]] = defaultdict(set)
        java_files = [f for f in source_files if f.extension == ".java"]
        
        # CallGraphBuilder에서 이미 파싱된 클래스 정보 재사용
        if self.call_graph_builder and self.call_graph_builder.file_to_classes_map:
            # 이미 파싱된 정보 사용
            for file_path_str, classes in self.call_graph_builder.file_to_classes_map.items():
                for cls in classes:
                    # 클래스명 -> 파일 경로 매핑
                    class_to_files[cls.name].add(file_path_str)
                    # 패키지 포함 전체 클래스명도 매핑
                    if cls.package:
                        full_class_name = f"{cls.package}.{cls.name}"
                        class_to_files[full_class_name].add(file_path_str)
        else:
            # CallGraphBuilder가 없거나 파싱되지 않은 경우에만 직접 파싱
            for java_file in java_files:
                try:
                    tree, error = self.java_parser.parse_file(java_file.path)
                    if error:
                        continue
                    
                    classes = self.java_parser.extract_class_info(tree, java_file.path)
                    for cls in classes:
                        # 클래스명 -> 파일 경로 매핑
                        class_to_files[cls.name].add(str(java_file.path))
                        # 패키지 포함 전체 클래스명도 매핑
                        if cls.package:
                            full_class_name = f"{cls.package}.{cls.name}"
                            class_to_files[full_class_name].add(str(java_file.path))
                except Exception as e:
                    self.logger.debug(f"Java 파일 파싱 중 오류 (무시): {java_file.path} - {e}")
        
        # XML 파일 분석
        xml_files = [f for f in source_files if f.extension == ".xml"]
        for xml_file in xml_files:
            try:
                result = self.xml_parser.parse_mapper_file(xml_file.path)
                if result.get("error"):
                    self.logger.warning(f"XML 파일 파싱 실패: {xml_file.path} - {result['error']}")
                    continue
                
                # SQL 쿼리에서 테이블명 추출
                for sql_query_info in result.get("sql_queries", []):
                    sql = sql_query_info.get("sql", "")
                    if sql:
                        tables = self.sql_strategy.extract_table_names(sql)
                        for table in tables:
                            file_table_map[str(xml_file.path)].add(table)
                
                # XML에서 class 정보 추출 (resultType, parameterType, resultMap)
                xml_classes = self._extract_classes_from_xml(result, xml_file.path)
                
                # 추출된 class들을 선언하거나 사용하는 Java 파일 찾기
                related_java_files = set()
                for class_name in xml_classes:
                    # 클래스명으로 파일 찾기
                    if class_name in class_to_files:
                        related_java_files.update(class_to_files[class_name])
                    # 패키지명 제거한 클래스명으로도 찾기
                    simple_class_name = class_name.split('.')[-1]
                    if simple_class_name in class_to_files:
                        related_java_files.update(class_to_files[simple_class_name])
                
                # Mapper interface 찾기 및 Call Graph를 통한 관련 파일 찾기
                mapper_interface_files = self._find_mapper_interfaces(related_java_files, source_files)
                related_java_files.update(mapper_interface_files)
                
                # Call Graph를 사용하여 Mapper interface를 사용하는 파일 찾기
                if self.call_graph_builder and self.call_graph_builder.call_graph:
                    dependent_files = self._find_files_using_mapper_interfaces(
                        mapper_interface_files, 
                        source_files
                    )
                    related_java_files.update(dependent_files)
                
                # 관련 Java 파일들을 테이블 접근 파일에 추가 (중복 제거됨)
                for sql_query_info in result.get("sql_queries", []):
                    sql = sql_query_info.get("sql", "")
                    if sql:
                        tables = self.sql_strategy.extract_table_names(sql)
                        for table in tables:
                            for java_file_path in related_java_files:
                                # 파일 경로를 문자열로 변환하여 일관성 유지
                                file_table_map[str(java_file_path)].add(table)
                
            except Exception as e:
                self.logger.error(f"XML 파일 분석 중 오류: {xml_file.path} - {e}")
        
        # Java 파일 분석 (SQL 쿼리가 포함된 경우)
        for java_file in java_files:
            try:
                # Java 파일에서 SQL 쿼리 추출 (주석, 문자열 리터럴 등)
                sql_queries = self._extract_sql_from_java(java_file.path)
                for sql in sql_queries:
                    tables = self.sql_strategy.extract_table_names(sql)
                    for table in tables:
                        file_table_map[str(java_file.path)].add(table)
            except Exception as e:
                self.logger.error(f"Java 파일 분석 중 오류: {java_file.path} - {e}")
        
        return dict(file_table_map)
    
    def _extract_sql_from_java(self, file_path: Path) -> List[str]:
        """
        Java 파일에서 SQL 쿼리 추출
        
        Args:
            file_path: Java 파일 경로
            
        Returns:
            List[str]: 추출된 SQL 쿼리 목록
        """
        sql_queries = []
        
        # 여러 인코딩 시도
        content = None
        encodings = ['utf-8', 'euc-kr', 'cp949', 'latin-1', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                content = file_path.read_text(encoding=encoding)
                break  # 성공하면 루프 종료
            except UnicodeDecodeError:
                continue  # 다음 인코딩 시도
            except Exception as e:
                # 다른 에러는 마지막 인코딩까지 시도 후 에러 반환
                if encoding == encodings[-1]:
                    self.logger.warning(f"Java 파일에서 SQL 추출 실패: {file_path} - {e}")
                    return sql_queries
                continue
        
        if content is None:
            self.logger.warning(f"Java 파일에서 SQL 추출 실패: {file_path} - 지원되는 인코딩을 찾을 수 없습니다")
            return sql_queries
        
        try:
            # 문자열 리터럴에서 SQL 쿼리 추출
            # "SELECT ..." 또는 'SELECT ...' 형식
            string_pattern = r'["\']([^"\']*(?:SELECT|INSERT|UPDATE|DELETE)[^"\']*)["\']'
            matches = re.findall(string_pattern, content, re.IGNORECASE | re.DOTALL)
            sql_queries.extend(matches)
            
            # 주석에서 SQL 쿼리 추출
            # /* SQL: SELECT ... */ 형식
            comment_pattern = r'/\*\s*SQL:\s*([^*]+)\s*\*/'
            comment_matches = re.findall(comment_pattern, content, re.IGNORECASE | re.DOTALL)
            sql_queries.extend(comment_matches)
            
        except Exception as e:
            self.logger.warning(f"Java 파일에서 SQL 추출 실패: {file_path} - {e}")
        
        return sql_queries
    
    def _extract_classes_from_xml(
        self, 
        xml_result: Dict[str, Any], 
        xml_file_path: Path
    ) -> Set[str]:
        """
        XML 파싱 결과에서 class 정보 추출 (resultType, parameterType, resultMap)
        
        Args:
            xml_result: XML 파서 결과
            xml_file_path: XML 파일 경로
            
        Returns:
            Set[str]: 추출된 클래스명 집합
        """
        classes = set()
        
        # SQL 쿼리에서 resultType, parameterType 추출
        for sql_query_info in xml_result.get("sql_queries", []):
            result_type = sql_query_info.get("result_type")
            parameter_type = sql_query_info.get("parameter_type")
            
            if result_type:
                # 패키지명 포함 전체 클래스명 또는 단순 클래스명
                classes.add(result_type)
                # 패키지명 제거한 클래스명도 추가
                simple_name = result_type.split('.')[-1]
                if simple_name != result_type:
                    classes.add(simple_name)
            
            if parameter_type:
                classes.add(parameter_type)
                simple_name = parameter_type.split('.')[-1]
                if simple_name != parameter_type:
                    classes.add(simple_name)
        
        # resultMap에서 type 속성 추출 및 mapper namespace 추출
        try:
            tree, error = self.xml_parser.parse_file(xml_file_path)
            if not error:
                root = tree.getroot()
                
                # mapper namespace 추출 (interface 이름으로 사용됨)
                namespace = root.get('namespace', '')
                if namespace:
                    # namespace는 보통 패키지.인터페이스명 형식
                    classes.add(namespace)
                    simple_name = namespace.split('.')[-1]
                    if simple_name != namespace:
                        classes.add(simple_name)
                
                # resultMap 요소 찾기
                result_maps = root.xpath(".//resultMap")
                for result_map in result_maps:
                    type_attr = result_map.get('type')
                    if type_attr:
                        classes.add(type_attr)
                        simple_name = type_attr.split('.')[-1]
                        if simple_name != type_attr:
                            classes.add(simple_name)
                
                # method element의 parameterType, resultType도 확인
                # (일부 XML에서는 method 태그를 사용)
                methods = root.xpath(".//method")
                for method in methods:
                    param_type = method.get('parameterType')
                    result_type = method.get('resultType')
                    if param_type:
                        classes.add(param_type)
                        simple_name = param_type.split('.')[-1]
                        if simple_name != param_type:
                            classes.add(simple_name)
                    if result_type:
                        classes.add(result_type)
                        simple_name = result_type.split('.')[-1]
                        if simple_name != result_type:
                            classes.add(simple_name)
        except Exception as e:
            self.logger.debug(f"XML class 정보 추출 중 오류 (무시): {xml_file_path} - {e}")
        
        return classes
    
    def _find_mapper_interfaces(
        self, 
        java_file_paths: Set[str], 
        source_files: List[SourceFile]
    ) -> Set[str]:
        """
        Java 파일 중 Mapper interface 찾기
        
        Args:
            java_file_paths: 확인할 Java 파일 경로 집합
            source_files: 전체 소스 파일 목록
            
        Returns:
            Set[str]: Mapper interface 파일 경로 집합
        """
        mapper_files = set()
        
        # 파일 경로를 Path로 변환하여 SourceFile 찾기
        path_to_file = {str(f.path): f for f in source_files}
        
        for file_path_str in java_file_paths:
            if file_path_str not in path_to_file:
                continue
            
            java_file = path_to_file[file_path_str]
            try:
                # CallGraphBuilder에서 이미 파싱된 클래스 정보 재사용
                if self.call_graph_builder:
                    classes = self.call_graph_builder.get_classes_for_file(java_file.path)
                else:
                    # CallGraphBuilder가 없으면 직접 파싱
                    tree, error = self.java_parser.parse_file(java_file.path)
                    if error:
                        continue
                    classes = self.java_parser.extract_class_info(tree, java_file.path)
                
                for cls in classes:
                    # 파일명이나 클래스명에 Mapper가 포함되어 있는지 확인
                    is_mapper_name = 'Mapper' in cls.name or 'Mapper' in java_file.filename
                    
                    if is_mapper_name:
                        # @Mapper, @Repository 어노테이션 확인
                        has_mapper_annotation = any(
                            'Mapper' in ann or 'Repository' in ann 
                            for ann in cls.annotations
                        )
                        
                        # interface인지 확인: interface는 보통 필드가 없고 메서드만 있음
                        # 또는 파일 내용에서 "interface" 키워드 확인
                        is_likely_interface = len(cls.fields) == 0 and len(cls.methods) > 0
                        
                        if has_mapper_annotation or (is_mapper_name and is_likely_interface):
                            mapper_files.add(file_path_str)
                            self.logger.debug(f"Mapper interface 발견: {file_path_str} (클래스: {cls.name})")
                            break
            except Exception as e:
                self.logger.debug(f"Mapper interface 확인 중 오류 (무시): {file_path_str} - {e}")
        
        return mapper_files
    
    def _find_files_using_mapper_interfaces(
        self, 
        mapper_interface_files: Set[str], 
        source_files: List[SourceFile]
    ) -> Set[str]:
        """
        Call Graph를 사용하여 Mapper interface를 사용하는 파일 찾기
        
        Args:
            mapper_interface_files: Mapper interface 파일 경로 집합
            source_files: 전체 소스 파일 목록
            
        Returns:
            Set[str]: Mapper interface를 사용하는 파일 경로 집합
        """
        dependent_files = set()
        
        if not self.call_graph_builder or not self.call_graph_builder.call_graph:
            return dependent_files
        
        # Mapper interface의 클래스명 추출
        mapper_class_names = set()
        path_to_file = {str(f.path): f for f in source_files}
        
        for file_path_str in mapper_interface_files:
            if file_path_str not in path_to_file:
                continue
            
            java_file = path_to_file[file_path_str]
            try:
                tree, error = self.java_parser.parse_file(java_file.path)
                if error:
                    continue
                
                classes = self.java_parser.extract_class_info(tree, java_file.path)
                for cls in classes:
                    mapper_class_names.add(cls.name)
                    if cls.package:
                        mapper_class_names.add(f"{cls.package}.{cls.name}")
            except Exception as e:
                self.logger.debug(f"Mapper 클래스명 추출 중 오류 (무시): {file_path_str} - {e}")
        
        # Call Graph에서 Mapper interface를 사용하는 메서드 찾기
        call_graph = self.call_graph_builder.call_graph
        method_metadata = self.call_graph_builder.method_metadata
        
        # Mapper interface의 메서드 시그니처 찾기
        mapper_methods = set()
        for method_sig, metadata in method_metadata.items():
            class_name = metadata.get("class_name", "")
            if class_name in mapper_class_names:
                mapper_methods.add(method_sig)
        
        # Mapper 메서드를 호출하는 파일 찾기
        for mapper_method in mapper_methods:
            # 이 메서드를 호출하는 노드 찾기 (역방향 탐색)
            if call_graph.has_node(mapper_method):
                # 이 노드를 호출하는 모든 노드 찾기
                predecessors = list(call_graph.predecessors(mapper_method))
                for caller in predecessors:
                    caller_metadata = method_metadata.get(caller, {})
                    file_path = caller_metadata.get("file_path", "")
                    if file_path:
                        dependent_files.add(file_path)
        
        # DAO, Service, Controller 레이어의 파일만 필터링
        filtered_files = set()
        for file_path_str in dependent_files:
            # 파일 경로로 SourceFile 찾기
            for source_file in source_files:
                if str(source_file.path) == file_path_str:
                    # 레이어 확인
                    layer = self._identify_layer(source_file)
                    if layer in ["DAO", "Service", "Controller"]:
                        filtered_files.add(file_path_str)
                    break
        
        return filtered_files
    
    def _assign_file_tags(
        self,
        source_files: List[SourceFile],
        file_table_map: Dict[str, Set[str]]
    ) -> List[SourceFile]:
        """
        각 파일에 접근하는 테이블명을 태그로 부여
        
        Args:
            source_files: 소스 파일 목록
            file_table_map: 파일-테이블 매핑
            
        Returns:
            List[SourceFile]: 태그가 부여된 소스 파일 목록
        """
        tagged_files = []
        
        for source_file in source_files:
            file_path_str = str(source_file.path)
            tables = file_table_map.get(file_path_str, set())
            
            # 태그 생성 (테이블명 리스트)
            tags = sorted([table for table in tables if table in self.table_column_map])
            
            # SourceFile 객체 복사 및 태그 추가
            tagged_file = SourceFile(
                path=source_file.path,
                relative_path=source_file.relative_path,
                filename=source_file.filename,
                extension=source_file.extension,
                size=source_file.size,
                modified_time=source_file.modified_time,
                tags=tags
            )
            tagged_files.append(tagged_file)
        
        return tagged_files
    
    def _classify_files_by_layer(
        self,
        source_files: List[SourceFile]
    ) -> Dict[str, List[SourceFile]]:
        """
        레이어별 파일 분류
        
        Args:
            source_files: 소스 파일 목록
            
        Returns:
            Dict[str, List[SourceFile]]: 레이어별 파일 목록
        """
        layer_files: Dict[str, List[SourceFile]] = defaultdict(list)
        
        for source_file in source_files:
            layer = self._identify_layer(source_file)
            layer_files[layer].append(source_file)
        
        return dict(layer_files)
    
    def _identify_layer(self, source_file: SourceFile) -> str:
        """
        파일의 레이어 식별
        
        Args:
            source_file: 소스 파일
            
        Returns:
            str: 레이어명 (Mapper, DTO, DAO, Service, Controller, Unknown)
        """
        file_path_str = str(source_file.path)
        filename = source_file.filename
        
        # 레이어 패턴 매칭
        for layer, patterns in self.LAYER_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, filename, re.IGNORECASE):
                    return layer
        
        # 경로 기반 분류 (확장자도 확인)
        path_lower = file_path_str.lower()
        # Mapper 레이어는 .xml 확장자만 허용
        if (("mapper" in path_lower or "xml" in path_lower) and source_file.extension == ".xml"):
            return "Mapper"
        elif "dto" in path_lower and source_file.extension == ".java":
            return "DTO"
        elif "dao" in path_lower and source_file.extension == ".java":
            return "DAO"
        elif "service" in path_lower and source_file.extension == ".java":
            return "Service"
        elif "controller" in path_lower and source_file.extension == ".java":
            return "Controller"
        
        return "Unknown"
    
    def _analyze_column_level(
        self,
        file_table_map: Dict[str, Set[str]],
        layer_files: Dict[str, List[SourceFile]]
    ) -> List[TableAccessInfo]:
        """
        칼럼 레벨 분석 및 TableAccessInfo 생성
        
        Args:
            file_table_map: 파일-테이블 매핑
            layer_files: 레이어별 파일 목록
            
        Returns:
            List[TableAccessInfo]: 테이블 접근 정보 목록
        """
        table_access_info_list = []
        
        # 테이블별로 그룹화
        table_file_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "files": set(),
            "columns": set(),
            "query_types": set(),
            "sql_queries": []
        })
        
        # XML 파일에서 정보 추출 (확장자가 .xml인 파일만 처리)
        mapper_files = layer_files.get("Mapper", [])
        xml_files = [f for f in mapper_files if f.extension == ".xml"]
        for xml_file in xml_files:
            try:
                result = self.xml_parser.parse_mapper_file(xml_file.path)
                if result.get("error"):
                    continue
                
                for sql_query_info in result.get("sql_queries", []):
                    sql = sql_query_info.get("sql", "")
                    query_type = sql_query_info.get("query_type", "")
                    
                    if sql:
                        tables = self.sql_strategy.extract_table_names(sql)
                        for table in tables:
                            if table in self.table_column_map:
                                table_file_map[table]["files"].add(str(xml_file.path))
                                table_file_map[table]["query_types"].add(query_type)
                                table_file_map[table]["sql_queries"].append(sql)
                                
                                # 칼럼 추출
                                columns = self.sql_strategy.extract_column_names(sql, table)
                                table_file_map[table]["columns"].update(columns)
            except Exception as e:
                self.logger.warning(f"XML 파일 칼럼 분석 실패: {xml_file.path} - {e}")
        
        # Java 파일에서 정보 추출
        java_files = []
        for layer in ["DAO", "Service", "Controller"]:
            java_files.extend(layer_files.get(layer, []))
        
        for java_file in java_files:
            try:
                sql_queries = self._extract_sql_from_java(java_file.path)
                for sql in sql_queries:
                    tables = self.sql_strategy.extract_table_names(sql)
                    for table in tables:
                        if table in self.table_column_map:
                            table_file_map[table]["files"].add(str(java_file.path))
                            columns = self.sql_strategy.extract_column_names(sql, table)
                            table_file_map[table]["columns"].update(columns)
            except Exception as e:
                self.logger.warning(f"Java 파일 칼럼 분석 실패: {java_file.path} - {e}")
        
        # TableAccessInfo 생성
        for table_name, info in table_file_map.items():
            # 레이어 결정 (대부분의 파일이 속한 레이어)
            layer = self._determine_layer_for_table(info["files"], layer_files)
            
            # 쿼리 타입 결정
            query_type = list(info["query_types"])[0] if info["query_types"] else "SELECT"
            
            table_access_info = TableAccessInfo(
                table_name=table_name,
                columns=sorted(list(info["columns"])),
                access_files=sorted(list(info["files"])),
                query_type=query_type,
                sql_query=info["sql_queries"][0] if info["sql_queries"] else None,
                layer=layer
            )
            table_access_info_list.append(table_access_info)
        
        return table_access_info_list
    
    def _determine_layer_for_table(
        self,
        file_paths: Set[str],
        layer_files: Dict[str, List[SourceFile]]
    ) -> str:
        """
        테이블 접근 파일들의 레이어 결정
        
        Args:
            file_paths: 파일 경로 집합
            layer_files: 레이어별 파일 목록
            
        Returns:
            str: 레이어명
        """
        layer_counts = defaultdict(int)
        
        for layer, files in layer_files.items():
            for file in files:
                if str(file.path) in file_paths:
                    layer_counts[layer] += 1
        
        if layer_counts:
            # 가장 많은 파일이 속한 레이어 반환
            return max(layer_counts.items(), key=lambda x: x[1])[0]
        
        return "Unknown"
    
    def _track_dependencies(
        self,
        table_access_info_list: List[TableAccessInfo],
        layer_files: Dict[str, List[SourceFile]]
    ) -> None:
        """
        테이블 접근 파일 간 의존성 추적
        
        Args:
            table_access_info_list: 테이블 접근 정보 목록
            layer_files: 레이어별 파일 목록
        """
        if not self.call_graph_builder or not self.call_graph_builder.call_graph:
            return
        
        # Call Graph를 활용하여 의존성 추적
        for table_info in table_access_info_list:
            # 각 파일에 대해 상위 레이어 파일 찾기
            dependent_files = set()
            
            for file_path in table_info.access_files:
                # Call Graph에서 이 파일을 호출하는 파일 찾기
                # (간단한 구현, 실제로는 더 복잡한 로직 필요)
                pass
            
            # 의존성 정보를 TableAccessInfo에 추가할 수 있음
            # (현재 TableAccessInfo 모델에는 의존성 필드가 없으므로 생략)

