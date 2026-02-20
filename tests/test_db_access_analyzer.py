"""
DB Access Analyzer 테스트

DB Access Analyzer의 기능을 테스트합니다.
"""

from datetime import datetime
from parser.call_graph_builder import CallGraphBuilder
from parser.java_ast_parser import JavaASTParser
from parser.xml_mapper_parser import XMLMapperParser
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, MagicMock, patch

import pytest

from analyzer.db_access_analyzer import DBAccessAnalyzer
from analyzer.sql_extractor import SQLExtractor
from config.config_manager import Configuration
from models.source_file import SourceFile
from persistence.cache_manager import CacheManager


@pytest.fixture
def temp_dir():
    """임시 디렉터리 생성"""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config(temp_dir):
    """샘플 Configuration 객체 생성"""
    return Configuration(
        target_project=str(temp_dir),
        source_file_types=[".java", ".xml"],
        sql_wrapping_type="mybatis",
        modification_type="ControllerOrService",
        access_tables=[
            {"table_name": "USERS", "columns": ["ID", "NAME", "EMAIL"]},
            {"table_name": "ORDERS", "columns": ["ORDER_ID", "USER_ID", "AMOUNT"]},
        ],
    )


@pytest.fixture
def cache_manager(temp_dir):
    """캐시 매니저 생성"""
    cache_dir = temp_dir / "cache"
    return CacheManager(cache_dir=cache_dir)


@pytest.fixture
def xml_parser(cache_manager):
    """XML Mapper 파서 생성"""
    return XMLMapperParser()


@pytest.fixture
def java_parser(cache_manager):
    """Java AST 파서 생성"""
    return JavaASTParser(cache_manager=cache_manager)


@pytest.fixture
def call_graph_builder(java_parser, cache_manager):
    """Call Graph Builder 생성"""
    return CallGraphBuilder(java_parser=java_parser, cache_manager=cache_manager)


@pytest.fixture
def mock_sql_extractor():
    """Mock SQL Extractor 생성"""
    extractor = Mock(spec=SQLExtractor)
    extractor.extract_table_names.return_value = set()
    extractor.extract_column_names.return_value = set()
    extractor.get_class_files_from_sql_query.return_value = (None, {}, set())
    return extractor


@pytest.fixture
def db_analyzer(sample_config, xml_parser, java_parser, call_graph_builder, mock_sql_extractor):
    """DB Access Analyzer 생성"""
    return DBAccessAnalyzer(
        config=sample_config,
        sql_extractor=mock_sql_extractor,
        xml_parser=xml_parser,
        java_parser=java_parser,
        call_graph_builder=call_graph_builder,
    )


@pytest.fixture
def sample_mapper_xml(temp_dir):
    """샘플 Mapper XML 파일 생성"""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.mapper.UserMapper">
    <select id="findById" resultType="User">
        SELECT id, name, email FROM users WHERE id = #{id}
    </select>
    <insert id="insert">
        INSERT INTO users (name, email) VALUES (#{name}, #{email})
    </insert>
</mapper>
"""
    xml_file = temp_dir / "UserMapper.xml"
    xml_file.write_text(xml_content, encoding="utf-8")
    return xml_file


@pytest.fixture
def sample_source_files(temp_dir, sample_mapper_xml):
    """샘플 소스 파일 목록 생성"""
    files = []

    # XML 파일
    xml_file = SourceFile(
        path=sample_mapper_xml,
        relative_path=sample_mapper_xml.name,
        filename=sample_mapper_xml.name,
        extension=".xml",
        size=sample_mapper_xml.stat().st_size,
        modified_time=datetime.fromtimestamp(sample_mapper_xml.stat().st_mtime),
        tags=[],
    )
    files.append(xml_file)

    # Java 파일
    java_file = temp_dir / "UserDAO.java"
    java_content = """
package com.example.dao;

@Repository
public class UserDAO {
    public User findById(Long id) {
        return null;
    }
}
"""
    java_file.write_text(java_content, encoding="utf-8")

    java_source_file = SourceFile(
        path=java_file,
        relative_path=java_file.name,
        filename=java_file.name,
        extension=".java",
        size=java_file.stat().st_size,
        modified_time=datetime.fromtimestamp(java_file.stat().st_mtime),
        tags=[],
    )
    files.append(java_source_file)

    return files


def test_db_analyzer_init(db_analyzer, sample_config):
    """DBAccessAnalyzer 초기화 테스트"""
    assert db_analyzer.config == sample_config
    assert db_analyzer.sql_extractor is not None
    assert "users" in db_analyzer.table_column_map
    assert "orders" in db_analyzer.table_column_map


def test_table_column_map(db_analyzer):
    """테이블-칼럼 매핑 테스트"""
    users_columns = db_analyzer.table_column_map.get("users", set())
    assert "id" in users_columns
    assert "name" in users_columns
    assert "email" in users_columns

    orders_columns = db_analyzer.table_column_map.get("orders", set())
    assert "order_id" in orders_columns
    assert "user_id" in orders_columns
    assert "amount" in orders_columns


def test_analyze_empty_results(db_analyzer, sample_source_files):
    """SQL 추출 결과가 없을 때 분석 테스트"""
    with patch(
        "analyzer.db_access_analyzer.DataPersistenceManager"
    ) as MockPersistence:
        mock_instance = MockPersistence.return_value
        mock_instance.load_from_file.return_value = None

        result = db_analyzer.analyze(sample_source_files)

        assert isinstance(result, list)
        assert len(result) == 0


def test_analyze_with_results(db_analyzer, sample_source_files, mock_sql_extractor):
    """SQL 추출 결과가 있을 때 분석 테스트"""
    mock_sql_extractor.extract_table_names.return_value = {"USERS"}
    mock_sql_extractor.extract_column_names.return_value = {"ID", "NAME"}

    sql_extraction_results = [
        {
            "file": {"path": "/path/to/UserMapper.xml"},
            "sql_queries": [
                {
                    "sql": "SELECT id, name, email FROM users WHERE id = 1",
                    "query_type": "SELECT",
                }
            ],
        }
    ]

    with patch(
        "analyzer.db_access_analyzer.DataPersistenceManager"
    ) as MockPersistence:
        mock_instance = MockPersistence.return_value
        mock_instance.load_from_file.return_value = sql_extraction_results

        result = db_analyzer.analyze(sample_source_files)

        assert isinstance(result, list)
        # 결과가 있으면 TableAccessInfo 객체인지 확인
        if result:
            assert hasattr(result[0], "table_name")
            assert hasattr(result[0], "columns")
            assert hasattr(result[0], "access_files")


def test_get_column_groups(db_analyzer):
    """칼럼 그룹 분류 테스트"""
    columns = {"id", "name", "email"}
    false_columns, true_columns = db_analyzer._get_column_groups("users", columns)

    # 기본적으로 모든 칼럼은 new_column=false
    assert len(false_columns) > 0
    assert len(true_columns) == 0


def test_determine_main_layer(db_analyzer):
    """주요 레이어 결정 테스트"""
    layer_files = {
        "dao": {"/path/to/UserDAO.java", "/path/to/OrderDAO.java"},
        "service": {"/path/to/UserService.java"},
    }
    main_layer = db_analyzer._determine_main_layer(layer_files)
    assert main_layer == "Dao"  # 파일이 더 많은 레이어

    # 빈 레이어
    assert db_analyzer._determine_main_layer({}) == "Unknown"
