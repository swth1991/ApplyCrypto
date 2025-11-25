"""
TableAccessInfo 데이터 모델

데이터베이스 테이블 접근 정보를 저장하는 데이터 모델입니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TableAccessInfo:
    """
    데이터베이스 테이블 접근 정보를 저장하는 데이터 모델
    
    Attributes:
        table_name: 테이블명
        columns: 접근하는 칼럼 목록
        access_files: 접근하는 파일 경로 목록
        query_type: 쿼리 타입 (SELECT, INSERT, UPDATE, DELETE)
        sql_query: SQL 쿼리 (선택적)
        layer: 레이어 정보 (Mapper, DAO, Service, Controller)
    """
    table_name: str
    columns: List[str]
    access_files: List[str]
    query_type: str
    sql_query: Optional[str] = None
    layer: str = ""
    
    def to_dict(self) -> dict:
        """딕셔너리 형태로 변환"""
        return {
            "table_name": self.table_name,
            "columns": self.columns,
            "access_files": self.access_files,
            "query_type": self.query_type,
            "sql_query": self.sql_query,
            "layer": self.layer
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TableAccessInfo":
        """딕셔너리로부터 TableAccessInfo 객체 생성"""
        return cls(
            table_name=data["table_name"],
            columns=data.get("columns", []),
            access_files=data.get("access_files", []),
            query_type=data["query_type"],
            sql_query=data.get("sql_query"),
            layer=data.get("layer", "")
        )

