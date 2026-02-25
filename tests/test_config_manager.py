"""
Configuration Manager 단위 테스트

다음 시나리오를 검증합니다:
1. 유효한 설정 직접 생성 성공
2. 필수 필드 누락 시 ValidationError 발생
3. 잘못된 JSON 형식 처리 (load_config)
4. 각 설정값의 정확한 파싱
5. 기본값 적용
6. 파일 없음 예외 처리 (load_config)
7. 잘못된 sql_wrapping_type 검증
8. 잘못된 access_tables 구조 검증
"""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from config.config_manager import Configuration, ConfigurationError, load_config


@pytest.fixture
def valid_config_data():
    """유효한 설정 데이터를 반환하는 픽스처"""
    return {
        "target_project": "/path/to/project",
        "source_file_types": [".java", ".xml"],
        "sql_wrapping_type": "mybatis",
        "modification_type": "ControllerOrService",
        "access_tables": [
            {"table_name": "EMPLOYEE", "columns": ["NAME", "JUMIN_NUMBER"]},
            {"table_name": "CUSTOMER", "columns": ["PHONE", "EMAIL"]},
        ],
    }


def test_load_valid_config(valid_config_data):
    """유효한 설정 데이터로 Configuration 직접 생성 성공 테스트"""
    config = Configuration(**valid_config_data)

    assert config.target_project == valid_config_data["target_project"]
    assert config.source_file_types == valid_config_data["source_file_types"]
    assert config.sql_wrapping_type == valid_config_data["sql_wrapping_type"]
    assert len(config.access_tables) == 2


def test_missing_required_field():
    """필수 필드 누락 시 ValidationError 발생 테스트"""
    # target_project 누락
    config_data = {
        "source_file_types": [".java"],
        "sql_wrapping_type": "mybatis",
        "modification_type": "ControllerOrService",
        "access_tables": [],
    }

    with pytest.raises(ValidationError):
        Configuration(**config_data)


def test_invalid_json_format():
    """잘못된 JSON 형식 처리 테스트 (load_config 사용)"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name

    try:
        with pytest.raises(ConfigurationError, match="JSON 형식이 올바르지 않습니다"):
            load_config(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_file_not_found():
    """파일 없음 예외 처리 테스트 (load_config 사용)"""
    with pytest.raises(ConfigurationError, match="설정 파일을 찾을 수 없습니다"):
        load_config("/nonexistent/path/config.json")


def test_property_access(valid_config_data):
    """각 설정값의 정확한 파싱 테스트"""
    config = Configuration(**valid_config_data)

    # target_project 프로퍼티 테스트
    assert isinstance(config.target_project, str)
    assert config.target_project == valid_config_data["target_project"]

    # source_file_types 프로퍼티 테스트
    assert isinstance(config.source_file_types, list)
    assert config.source_file_types == [".java", ".xml"]

    # sql_wrapping_type 프로퍼티 테스트
    assert config.sql_wrapping_type == "mybatis"

    # modification_type 프로퍼티 테스트
    assert config.modification_type == "ControllerOrService"

    # access_tables 프로퍼티 테스트 (Pydantic 모델 속성 접근)
    assert len(config.access_tables) == 2
    assert config.access_tables[0].table_name == "EMPLOYEE"
    assert config.access_tables[0].columns == ["NAME", "JUMIN_NUMBER"]


def test_get_table_names(valid_config_data):
    """테이블명 목록 조회 테스트"""
    config = Configuration(**valid_config_data)

    table_names = config.get_table_names()
    assert "EMPLOYEE" in table_names
    assert "CUSTOMER" in table_names
    assert len(table_names) == 2


def test_get_columns_for_table(valid_config_data):
    """특정 테이블의 칼럼 목록 조회 테스트"""
    config = Configuration(**valid_config_data)

    # 존재하는 테이블
    columns = config.get_columns_for_table("EMPLOYEE")
    assert "NAME" in columns
    assert "JUMIN_NUMBER" in columns

    # 존재하지 않는 테이블
    columns = config.get_columns_for_table("NONEXISTENT")
    assert columns == []


def test_invalid_sql_wrapping_type():
    """잘못된 sql_wrapping_type 값 처리 테스트"""
    config_data = {
        "target_project": "/path/to/project",
        "source_file_types": [".java"],
        "sql_wrapping_type": "invalid_type",
        "modification_type": "ControllerOrService",
        "access_tables": [],
    }

    with pytest.raises(ValidationError):
        Configuration(**config_data)


def test_invalid_access_tables_structure():
    """잘못된 access_tables 구조 처리 테스트"""
    config_data = {
        "target_project": "/path/to/project",
        "source_file_types": [".java"],
        "sql_wrapping_type": "mybatis",
        "modification_type": "ControllerOrService",
        "access_tables": [
            {
                "table_name": "EMPLOYEE"
                # columns 필드 누락
            }
        ],
    }

    with pytest.raises(ValidationError):
        Configuration(**config_data)


def test_default_values():
    """기본값 적용 테스트"""
    config_data = {
        "target_project": "/path/to/project",
        "source_file_types": [".java"],
        "sql_wrapping_type": "mybatis",
        "modification_type": "ControllerOrService",
        "access_tables": [],
    }

    config = Configuration(**config_data)

    # 기본값 확인
    assert config.framework_type == "SpringMVC"
    assert config.llm_provider == "watsonx_ai"
    assert config.exclude_dirs == []
    assert config.exclude_files == []
    assert config.use_call_chain_mode is False
    assert config.use_llm_parser is False
    assert config.max_tokens_per_batch == 8000
    assert config.max_workers == 4
    assert config.max_retries == 3
    assert config.generate_type == "diff"
    assert config.ccs_prefix is None
    assert config.type_handler is None
    assert config.two_step_config is None
    assert config.three_step_config is None
