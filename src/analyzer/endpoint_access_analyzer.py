"""
Endpoint Access Analyzer 모듈

각 엔드포인트별로 접근하는 파일, XML 파일, 테이블 정보를 분석하고
마크다운 리포트를 생성합니다.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from models.table_access_info import TableAccessInfo


class EndpointAccessAnalyzer:
    """
    엔드포인트별 접근 정보를 분석하는 클래스

    Call Graph, SQL 추출 결과, 테이블 접근 정보를 기반으로
    각 엔드포인트가 어떤 파일과 XML 쿼리에 접근하는지 분석합니다.
    """

    def analyze(
        self,
        call_graph_data: Dict[str, Any],
        sql_extraction_results: List[Dict[str, Any]],
        table_access_info_list: List[TableAccessInfo],
    ) -> List[Dict[str, Any]]:
        """
        각 엔드포인트별 전체 접근 경로 정보 수집

        call_graph의 call_trees를 순회하면서 각 엔드포인트가 접근하는
        모든 파일, XML 파일, 테이블 정보를 수집합니다.

        Args:
            call_graph_data: call_graph.json 데이터
            sql_extraction_results: SQL 추출 결과
            table_access_info_list: 테이블 접근 정보 목록

        Returns:
            List[Dict[str, Any]]: 엔드포인트별 접근 정보 목록
        """
        endpoint_access_list = []

        # call_trees에서 각 엔드포인트 정보 순회
        call_trees = call_graph_data.get("call_trees", [])

        # XML 파일 경로별 쿼리 매핑 생성
        xml_file_queries: Dict[str, List[Dict[str, Any]]] = {}
        for result in sql_extraction_results:
            file_info = result.get("file", {})
            file_path = file_info.get("path", "")
            if file_path.endswith(".xml"):
                if file_path not in xml_file_queries:
                    xml_file_queries[file_path] = []
                xml_file_queries[file_path].extend(result.get("sql_queries", []))

        # 관심 테이블 목록 수집 (config.json에서 설정된 테이블)
        target_tables: Set[str] = set()
        for table_info in table_access_info_list:
            target_tables.add(table_info.table_name.lower())

        for tree in call_trees:
            endpoint_info = tree.get("endpoint", {})
            if not endpoint_info:
                continue

            # 트리를 순회하며 접근 파일 및 메서드 수집
            accessed_files: List[Dict[str, Any]] = []
            xml_files_accessed: List[Dict[str, Any]] = []
            tables_accessed: Set[str] = set()
            visited_files: Set[str] = set()
            visited_method_names: Set[str] = (
                set()
            )  # 호출되는 메서드명 수집 (쿼리 id 매칭용)
            visited_methods: Set[str] = set()  # 중복 메서드 호출 방지

            def traverse_tree(node: Dict[str, Any], depth: int = 0) -> None:
                """재귀적으로 트리를 순회하며 파일 정보 수집 (depth 포함)"""
                method_sig = node.get("method_signature", "")
                file_path = node.get("file_path", "")
                class_name = node.get("class_name", "")

                # 메서드명 수집 (예: RecordMapper.getRecordsByPage -> getRecordsByPage)
                if method_sig and "." in method_sig:
                    method_name = method_sig.split(".")[-1]
                    visited_method_names.add(method_name)

                # 동일한 메서드 시그니처는 한 번만 수집 (파일 기준이 아닌 메서드 기준)
                if method_sig and method_sig not in visited_methods:
                    visited_methods.add(method_sig)
                    if file_path:
                        visited_files.add(file_path)
                    accessed_files.append(
                        {
                            "file_path": file_path,
                            "class_name": class_name,
                            "method_signature": method_sig,
                            "depth": depth,  # 실제 호출 depth 저장
                        }
                    )

                # 자식 노드 순회 (depth 증가)
                for child in node.get("children", []):
                    traverse_tree(child, depth + 1)

            # 루트 노드부터 순회
            traverse_tree(tree)

            # 접근한 파일에서 클래스명 추출 (Mapper 인터페이스와 XML namespace 매칭용)
            visited_class_names: set = set()
            for accessed_file in accessed_files:
                class_name = accessed_file.get("class_name", "")
                if class_name:
                    visited_class_names.add(class_name)

            # SQL 추출 결과에서 해당 Mapper와 연결된 XML 파일 찾기
            # XML 파일별로 매칭되는 쿼리를 모아둠 (같은 XML이 여러 result에 분리될 수 있음)
            xml_queries_map: Dict[str, List[Dict[str, Any]]] = {}
            matched_query_ids: Set[str] = set()  # 중복 쿼리 방지

            for result in sql_extraction_results:
                file_info = result.get("file", {})
                xml_file_path = file_info.get("path", "")

                # XML 파일인 경우에만 처리
                if not xml_file_path.endswith(".xml"):
                    continue

                # 해당 XML의 SQL 쿼리들 중 실제로 호출되고 관심 테이블에 접근하는 것만 찾기
                for sql_query in result.get("sql_queries", []):
                    strategy_specific = sql_query.get("strategy_specific", {})
                    namespace = strategy_specific.get("namespace", "")
                    query_id = sql_query.get("id", "")

                    # namespace에서 클래스명 추출 (예: com.mybatis.dao.EmployeeMapper -> EmployeeMapper)
                    if namespace:
                        mapper_class_name = namespace.split(".")[-1]

                        # 중복 쿼리 체크 (같은 XML의 같은 쿼리가 여러 result에 있을 수 있음)
                        query_key = f"{xml_file_path}:{mapper_class_name}:{query_id}"
                        if query_key in matched_query_ids:
                            continue

                        # 매칭 조건:
                        # 1. 접근한 클래스 중에 이 Mapper가 있고
                        # 2. 쿼리 id가 호출된 메서드명과 일치해야 함
                        if (
                            mapper_class_name in visited_class_names
                            and query_id in visited_method_names
                        ):
                            # SQL에서 테이블 추출
                            sql_text = sql_query.get("sql", "")
                            query_tables = self._extract_tables_from_sql(sql_text)

                            # 관심 테이블과 교집합이 있는 경우에만 포함
                            matched_tables = query_tables.intersection(target_tables)
                            if matched_tables:
                                # XML 파일별로 쿼리 수집
                                if xml_file_path not in xml_queries_map:
                                    xml_queries_map[xml_file_path] = []

                                xml_queries_map[xml_file_path].append(
                                    {
                                        "id": query_id,
                                        "query_type": sql_query.get("query_type", ""),
                                        "sql": sql_text,
                                    }
                                )
                                matched_query_ids.add(query_key)
                                # 매칭된 관심 테이블만 추가
                                tables_accessed.update(matched_tables)

            # 수집된 XML 파일과 쿼리 정보를 결과에 추가
            for xml_file_path, queries in xml_queries_map.items():
                xml_files_accessed.append(
                    {"file_path": xml_file_path, "queries": queries}
                )

            # 관심 쿼리를 호출하는 엔드포인트만 결과에 포함 (XML 쿼리에서 추출한 테이블 기준)
            if xml_files_accessed:
                endpoint_access_list.append(
                    {
                        "endpoint": endpoint_info,
                        "accessed_files": accessed_files,
                        "call_tree": tree,  # 원본 트리 구조 저장 (정확한 호출 관계용)
                        "xml_files": xml_files_accessed,
                        "tables_accessed": sorted(list(tables_accessed)),
                        "total_files_count": len(accessed_files),
                        "total_xml_files_count": len(xml_files_accessed),
                    }
                )

        return endpoint_access_list

    def generate_report(
        self,
        endpoint_access_info: List[Dict[str, Any]],
        output_path: Path,
    ) -> None:
        """
        엔드포인트별 접근 정보를 마크다운 형식으로 출력

        Args:
            endpoint_access_info: 엔드포인트별 접근 정보 목록
            output_path: 출력 파일 경로
        """
        lines = []

        # 마크다운 헤더
        lines.append("# 엔드포인트별 접근 정보 리포트")
        lines.append("")
        lines.append(
            f"> **총 {len(endpoint_access_info)}개 엔드포인트**가 관심 테이블에 접근합니다."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # 목차 생성
        lines.append("## 목차")
        lines.append("")
        for idx, ep_info in enumerate(endpoint_access_info, 1):
            endpoint = ep_info.get("endpoint", {})
            http_method = endpoint.get("http_method", "")
            path = endpoint.get("path", "")
            anchor = f"endpoint-{idx}"
            lines.append(f"{idx}. [{http_method} {path}](#{anchor})")
        lines.append("")
        lines.append("---")
        lines.append("")

        for idx, ep_info in enumerate(endpoint_access_info, 1):
            endpoint = ep_info.get("endpoint", {})
            call_tree = ep_info.get("call_tree", {})  # 원본 트리 구조
            xml_files = ep_info.get("xml_files", [])
            tables = ep_info.get("tables_accessed", [])

            # 엔드포인트 헤더
            http_method = endpoint.get("http_method", "")
            path = endpoint.get("path", "")
            method_sig = endpoint.get("method_signature", "")

            lines.append(f"## {idx}. {http_method} `{path}` {{#endpoint-{idx}}}")
            lines.append("")
            lines.append(f"**Entry Point:** `{method_sig}`")
            lines.append("")

            # 접근 테이블 정보
            if tables:
                lines.append(f"**접근 테이블:** `{', '.join(tables)}`")
                lines.append("")

            # Call Tree 형식으로 접근 파일 출력
            lines.append("### 호출 경로 (Call Tree)")
            lines.append("")
            lines.append("```")

            # 원본 call_tree 렌더링
            if call_tree:
                tree_lines = self._render_call_tree(call_tree)
                lines.extend(tree_lines)
            else:
                lines.append("(호출 트리 정보 없음)")

            lines.append("```")
            lines.append("")

            # XML 파일 및 쿼리 정보
            if xml_files:
                lines.append("### XML Mapper 쿼리")
                lines.append("")

                for xml_info in xml_files:
                    xml_path = xml_info.get("file_path", "")
                    queries = xml_info.get("queries", [])
                    xml_filename = xml_path.split("/")[-1] if xml_path else ""

                    lines.append(f"#### 📄 `{xml_filename}`")
                    lines.append("")

                    for query in queries:
                        query_id = query.get("id", "")
                        query_type = query.get("query_type", "").upper()
                        sql = query.get("sql", "")

                        lines.append(f"**`{query_id}`** ({query_type})")
                        lines.append("")
                        lines.append("```sql")
                        # SQL 포맷팅 (들여쓰기 유지)
                        sql_formatted = sql.strip()
                        lines.append(sql_formatted)
                        lines.append("```")
                        lines.append("")

            lines.append("---")
            lines.append("")

        # 파일에 쓰기 (.md 확장자로 변경)
        md_output_path = output_path.with_suffix(".md")
        with open(md_output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _extract_tables_from_sql(self, sql: str) -> Set[str]:
        """
        SQL 문에서 테이블명 추출

        FROM, JOIN, INTO, UPDATE 등 뒤에 오는 테이블명을 추출합니다.

        Args:
            sql: SQL 쿼리 문자열

        Returns:
            Set[str]: 추출된 테이블명 집합 (소문자)
        """
        tables: Set[str] = set()
        if not sql:
            return tables

        # SQL 정규화 (줄바꿈, 탭 -> 공백, 여러 공백 -> 단일 공백)
        normalized_sql = re.sub(r"\s+", " ", sql.upper())

        # 테이블명 추출 패턴들
        patterns = [
            r"FROM\s+([A-Z_][A-Z0-9_]*)",  # FROM table
            r"JOIN\s+([A-Z_][A-Z0-9_]*)",  # JOIN table
            r"INTO\s+([A-Z_][A-Z0-9_]*)",  # INSERT INTO table
            r"UPDATE\s+([A-Z_][A-Z0-9_]*)",  # UPDATE table
            r"FROM\s+([A-Z_][A-Z0-9_]*)\s*,",  # FROM table1, table2
            r",\s*([A-Z_][A-Z0-9_]*)\s+(?:WHERE|ON|SET|ORDER|GROUP|HAVING|LIMIT|$)",  # , table WHERE
        ]

        for pattern in patterns:
            matches = re.findall(pattern, normalized_sql)
            for match in matches:
                # 예약어 제외
                reserved_words = {
                    "SELECT",
                    "FROM",
                    "WHERE",
                    "AND",
                    "OR",
                    "NOT",
                    "IN",
                    "ON",
                    "SET",
                    "VALUES",
                    "AS",
                    "LEFT",
                    "RIGHT",
                    "INNER",
                    "OUTER",
                    "CROSS",
                    "ORDER",
                    "GROUP",
                    "BY",
                    "HAVING",
                    "LIMIT",
                    "OFFSET",
                    "UNION",
                    "DISTINCT",
                }
                if match not in reserved_words:
                    tables.add(match.lower())

        return tables

    def _is_vo_class(self, class_name: str) -> bool:
        """VO, DTO, Entity 등의 데이터 클래스인지 판별"""
        if not class_name:
            return False
        # 대소문자 무시하고 패턴 매칭
        class_name_lower = class_name.lower()
        vo_patterns = ["vo", "dto", "entity", "model", "bean", "pojo"]
        # 클래스명이 패턴으로 끝나는 경우
        for pattern in vo_patterns:
            if class_name_lower.endswith(pattern):
                return True
        return False

    def _render_call_tree(
        self,
        node: Dict[str, Any],
        prefix: str = "",
        is_last: bool = True,
        is_root: bool = True,
        visited: Optional[set] = None,
    ) -> List[str]:
        """원본 call_tree를 재귀적으로 렌더링 (정확한 부모-자식 관계, VO 제외)"""
        if visited is None:
            visited = set()

        result: List[str] = []
        node_method_sig = node.get("method_signature", "")
        node_file_path = node.get("file_path", "")
        node_class_name = node.get("class_name", "")
        filename = node_file_path.split("/")[-1] if node_file_path else ""

        # 클래스명이 없거나 VO 클래스인 경우 자식만 처리 (현재 노드는 스킵)
        if (
            not node_class_name
            or not node_method_sig
            or self._is_vo_class(node_class_name)
        ):
            children = node.get("children", [])
            valid_children = [
                c
                for c in children
                if c.get("class_name")
                and c.get("method_signature")
                and not self._is_vo_class(c.get("class_name", ""))
            ]
            for i, child in enumerate(valid_children):
                is_child_last = i == len(valid_children) - 1
                result.extend(
                    self._render_call_tree(
                        child, prefix, is_child_last, is_root, visited
                    )
                )
            return result

        # 순환 참조 방지
        if node_method_sig in visited:
            return result
        visited.add(node_method_sig)

        # 메서드명 추출
        if "." in node_method_sig:
            method_name = node_method_sig.split(".")[-1]
        else:
            method_name = node_method_sig

        # 노드 출력
        if is_root:
            result.append(f"{node_class_name}.{method_name} ({filename})")
            child_prefix = ""
        else:
            connector = "└── " if is_last else "├── "
            result.append(
                f"{prefix}{connector}{node_class_name}.{method_name} ({filename})"
            )
            child_prefix = prefix + ("    " if is_last else "│   ")

        # 자식 노드 처리 (유효한 자식만, VO 제외)
        children = node.get("children", [])
        valid_children = [
            c
            for c in children
            if c.get("class_name")
            and c.get("method_signature")
            and not self._is_vo_class(c.get("class_name", ""))
        ]

        for i, child in enumerate(valid_children):
            is_child_last = i == len(valid_children) - 1
            result.extend(
                self._render_call_tree(
                    child, child_prefix, is_child_last, False, visited.copy()
                )
            )

        return result
