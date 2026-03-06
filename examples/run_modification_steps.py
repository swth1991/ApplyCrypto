"""
Modification Steps 실행 스크립트

1단계: VO 파일에서 테이블/컬럼에 대응되는 property를 찾아서 vo_info를 생성합니다.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from config.config_manager import load_config
from models.code_generator import CodeGeneratorInput
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from modifier.code_modifier import CodeModifier
from modifier.llm.llm_factory import create_llm_provider
from persistence.data_persistence_manager import DataPersistenceManager

# Add src to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root / "src"))

# Load .env
load_dotenv(project_root / ".env")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_modification_steps")


def filter_vo_files(repository_files: List[str]) -> List[str]:
    """
    repository 파일 목록에서 "model"이나 "vo"가 포함된 파일들을 필터링합니다.

    Args:
        repository_files: repository 파일 경로 목록

    Returns:
        필터링된 VO/Model 파일 경로 목록
    """
    vo_files = []
    for file_path in repository_files:
        file_path_lower = file_path.lower()
        if "beans" in file_path_lower or "vo" in file_path_lower:
            vo_files.append(file_path)
    return vo_files


def read_file_content(file_path: str, target_project_path: Optional[Path] = None) -> str:
    """
    파일 내용을 읽어서 반환합니다.

    Args:
        file_path: 파일 경로 (절대 또는 상대 경로)
        target_project_path: 타겟 프로젝트 경로 (상대 경로인 경우 사용)

    Returns:
        파일 내용 (UTF-8)
    """
    try:
        # 절대 경로인지 확인
        path = Path(file_path)
        if not path.is_absolute() and target_project_path:
            # 상대 경로인 경우 target_project 기준으로 절대 경로 생성
            path = target_project_path / file_path
        
        if not path.exists():
            logger.warning(f"파일을 찾을 수 없습니다: {path}")
            return ""
        
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"파일 읽기 실패: {file_path} - {e}")
        return ""


def build_prompt(
    table_name: str, columns: List[Dict[str, Any]], vo_file_contents: Dict[str, str]
) -> str:
    """
    LLM에 전달할 프롬프트를 생성합니다.

    Args:
        table_name: 테이블명
        columns: 컬럼 정보 목록
        vo_file_contents: VO 파일 경로를 key로 하는 파일 내용 딕셔너리

    Returns:
        생성된 프롬프트 문자열
    """
    column_names = [col.get("name", "") if isinstance(col, dict) else col for col in columns]
    column_names_str = ", ".join(column_names)

    prompt = f"""Analyze the following Java VO files and find properties that correspond to the columns ({column_names_str}) of table "{table_name}".

For each VO file:
1. Find the public class name.
2. Find properties that correspond to each column name (case-insensitive matching).
3. Find getter and setter methods for each property.

Return the analysis results in the following JSON format:
{{
  "vo_info": [
    {{
      "class_name": "<public class name>",
      "properties": [
        {{
          "name": "<property name>",
          "getter": "<getter method name>",
          "setter": "<setter method name>"
        }}
      ]
    }}
  ]
}}

VO file list:
"""

    # VO 파일들을 특정 형식으로 추가
    for file_path, content in vo_file_contents.items():
        file_name = Path(file_path).name
        prompt += f"""
==== FILE : {file_name} ====
{content}
===================
"""

    return prompt


def parse_llm_response(response_content: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON을 추출하고 파싱합니다.

    Args:
        response_content: LLM 응답 내용

    Returns:
        파싱된 vo_info 딕셔너리
    """
    try:
        # JSON 코드 블록에서 JSON 추출 시도
        json_match = re.search(r"\{[\s\S]*\"vo_info\"[\s\S]*\}", response_content)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        
        # 전체 내용을 JSON으로 파싱 시도
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 파싱 실패: {e}")
        logger.debug(f"응답 내용: {response_content}")
        # 빈 vo_info 반환
        return {"vo_info": []}


def analyze_vo_files(
    llm_provider,
    table_name: str,
    columns: List[Dict[str, Any]],
    vo_files: List[str],
    target_project_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    VO 파일들을 LLM으로 분석하여 vo_info를 추출합니다.

    Args:
        llm_provider: LLM 프로바이더 인스턴스
        table_name: 테이블명
        columns: 컬럼 정보 목록
        vo_files: VO 파일 경로 목록
        target_project_path: 타겟 프로젝트 경로 (상대 경로인 경우 사용)

    Returns:
        vo_info 딕셔너리
    """
    if not vo_files:
        logger.info(f"테이블 '{table_name}'에 대한 VO 파일이 없습니다.")
        return {"vo_info": []}

    # VO 파일들 읽기
    vo_file_contents = {}
    for file_path in vo_files:
        content = read_file_content(file_path, target_project_path)
        if content:
            vo_file_contents[file_path] = content

    if not vo_file_contents:
        logger.warning(f"테이블 '{table_name}'에 대한 VO 파일 내용을 읽을 수 없습니다.")
        return {"vo_info": []}

    # 프롬프트 생성
    prompt = build_prompt(table_name, columns, vo_file_contents)

    logger.info(f"테이블 '{table_name}'에 대한 VO 파일 분석 시작 (파일 수: {len(vo_file_contents)})")

    try:
        # LLM 호출
        response = llm_provider.call(prompt)
        response_content = response.get("content", "")

        # 응답 파싱
        vo_info = parse_llm_response(response_content)

        logger.info(f"테이블 '{table_name}'에 대한 VO 분석 완료")
        return vo_info

    except Exception as e:
        logger.error(f"LLM 분석 중 오류 발생: {e}")
        return {"vo_info": []}


def build_sql_analysis_prompt(
    table_name: str, vo_info: List[Dict[str, Any]], sql_query: str
) -> str:
    """
    SQL 쿼리 분석을 위한 프롬프트를 생성합니다.

    Args:
        table_name: 테이블명
        vo_info: VO 정보 리스트
        sql_query: SQL 쿼리

    Returns:
        생성된 프롬프트 문자열
    """
    vo_info_json = json.dumps(vo_info, indent=2, ensure_ascii=False)

    prompt = f"""Analyze the following SQL query and determine which properties from the VO classes are actually used in the query, and whether column aliases are used.

Table name: {table_name}

VO Information:
{vo_info_json}

SQL Query:
{sql_query}

For each property in the VO classes:
1. Check if the property's corresponding column is actually used in the SQL query (used_in_query: true/false).
2. Check if the column uses an alias in the query (used_alias: alias name or empty string "").
3. If an alias is used, update the getter and setter method names to match the alias naming convention.

Return the analysis results in the following JSON format:
{{
  "used_vo_info": [
    {{
      "class_name": "<public class name>",
      "properties": [
        {{
          "name": "<property name>",
          "getter": "<getter method name>",
          "setter": "<setter method name>",
          "used_in_query": true/false,
          "used_alias": "<alias name or empty string>"
        }}
      ]
    }}
  ]
}}
"""

    return prompt


def parse_sql_analysis_response(response_content: str) -> Dict[str, Any]:
    """
    SQL 분석 LLM 응답에서 JSON을 추출하고 파싱합니다.

    Args:
        response_content: LLM 응답 내용

    Returns:
        파싱된 used_vo_info 딕셔너리
    """
    try:
        # JSON 코드 블록에서 JSON 추출 시도
        json_match = re.search(r"\{[\s\S]*\"used_vo_info\"[\s\S]*\}", response_content)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)

        # 전체 내용을 JSON으로 파싱 시도
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 파싱 실패: {e}")
        logger.debug(f"응답 내용: {response_content}")
        # 빈 used_vo_info 반환
        return {"used_vo_info": []}


def analyze_sql_query(
    llm_provider,
    table_name: str,
    vo_info: List[Dict[str, Any]],
    sql_query: str,
) -> List[Dict[str, Any]]:
    """
    SQL 쿼리를 분석하여 used_vo_info를 생성합니다.

    Args:
        llm_provider: LLM 프로바이더 인스턴스
        table_name: 테이블명
        vo_info: VO 정보 리스트
        sql_query: SQL 쿼리

    Returns:
        used_vo_info 리스트
    """
    if not vo_info:
        logger.info(f"테이블 '{table_name}'에 대한 vo_info가 없습니다.")
        return []

    if not sql_query:
        logger.info(f"SQL 쿼리가 없습니다.")
        return []

    # 프롬프트 생성
    prompt = build_sql_analysis_prompt(table_name, vo_info, sql_query)

    logger.info(f"테이블 '{table_name}'에 대한 SQL 쿼리 분석 시작")

    try:
        # LLM 호출
        response = llm_provider.call(prompt)
        response_content = response.get("content", "")

        # 응답 파싱
        result = parse_sql_analysis_response(response_content)
        used_vo_info = result.get("used_vo_info", [])

        logger.info(f"테이블 '{table_name}'에 대한 SQL 쿼리 분석 완료")
        return used_vo_info

    except Exception as e:
        logger.error(f"LLM 분석 중 오류 발생: {e}")
        return []


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Modification Steps 실행 - 1단계: VO 파일 분석, 2단계: SQL 쿼리 분석"
    )
    parser.add_argument(
        "--config", type=str, default="config.json", help="Path to config.json"
    )
    parser.add_argument(
        "--mock", action="store_true", help="Force use of mock LLM provider"
    )

    args = parser.parse_args()

    # Config 파일 경로 확인
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        if (project_root / args.config).exists():
            config_path = project_root / args.config
        else:
            logger.error(f"Config 파일을 찾을 수 없습니다: {config_path}")
            return 1

    # Config 로드
    try:
        config = load_config(str(config_path))
        if args.mock:
            config.llm_provider = "mock"
            logger.info("LLM Provider를 'mock'으로 강제 설정합니다.")

        logger.info(f"Config 로드 완료: {config_path}")
        logger.info(f"Target Project: {config.target_project}")
        logger.info(f"LLM Provider: {config.llm_provider}")
    except Exception as e:
        logger.error(f"Config 로드 실패: {e}")
        return 1

    # Target project 경로 설정
    target_project_path = Path(config.target_project)
    results_dir = target_project_path / ".applycrypto" / "results"
    table_access_info_path = results_dir / "table_access_info.json"

    # table_access_info.json 파일 확인
    if not table_access_info_path.exists():
        logger.error(f"table_access_info.json 파일을 찾을 수 없습니다: {table_access_info_path}")
        return 1

    # DataPersistenceManager 초기화
    try:
        persistence_manager = DataPersistenceManager(
            target_project=target_project_path,
            output_dir=results_dir,
        )
    except Exception as e:
        logger.error(f"DataPersistenceManager 초기화 실패: {e}")
        return 1

    # table_access_info.json 로드
    try:
        table_access_info_list = persistence_manager.load_from_file(
            "table_access_info.json", TableAccessInfo
        )
        if not table_access_info_list:
            logger.warning("table_access_info.json에 데이터가 없습니다.")
            return 0

        logger.info(f"table_access_info.json 로드 완료: {len(table_access_info_list)}개 항목")
    except Exception as e:
        logger.error(f"table_access_info.json 로드 실패: {e}")
        return 1

    # LLM Provider 초기화
    try:
        llm_provider = create_llm_provider(config.llm_provider)
        logger.info(f"LLM Provider 초기화 완료: {llm_provider.get_provider_name()}")
    except Exception as e:
        logger.error(f"LLM Provider 초기화 실패: {e}")
        return 1

    # 각 항목에 대해 VO 파일 분석 수행
    updated_count = 0
    for table_info in table_access_info_list:
        table_name = table_info.table_name
        columns = table_info.columns
        layer_files = table_info.layer_files or {}

        # repository 파일 목록 가져오기
        repository_files = layer_files.get("repository", [])
        if not repository_files:
            logger.info(f"테이블 '{table_name}'에 대한 repository 파일이 없습니다.")
            continue

        # VO/Model 파일 필터링
        vo_files = filter_vo_files(repository_files)
        if not vo_files:
            logger.info(f"테이블 '{table_name}'에 대한 VO/Model 파일이 없습니다.")
            continue

        logger.info(f"테이블 '{table_name}': {len(vo_files)}개 VO/Model 파일 발견")

        # VO 파일 분석
        vo_info_result = analyze_vo_files(
            llm_provider, table_name, columns, vo_files, target_project_path
        )
        vo_info_list = vo_info_result.get("vo_info", [])

        # table_info에 vo_info 추가 (딕셔너리로 변환 후 vo_info 필드 추가)
        # 나중에 저장할 때 vo_info를 포함하기 위해 딕셔너리에 저장
        table_dict = table_info.to_dict()
        table_dict["vo_info"] = vo_info_list
        
        # 임시로 vo_info를 table_info 객체에 저장 (저장 시 사용)
        # TableAccessInfo 모델에는 vo_info 필드가 없으므로, 딕셔너리로 관리
        if not hasattr(table_info, "_vo_info"):
            table_info._vo_info = vo_info_list
        else:
            table_info._vo_info = vo_info_list
        
        updated_count += 1

        logger.info(
            f"테이블 '{table_name}': vo_info 추가 완료 ({len(vo_info_list)}개 클래스)"
        )

    # 수정된 table_access_info.json 저장
    try:
        # TableAccessInfo 객체 리스트를 딕셔너리 리스트로 변환 (vo_info 포함)
        data_to_save = []
        for table_info in table_access_info_list:
            table_dict = table_info.to_dict()
            
            # vo_info가 추가된 경우 access_files 다음에 삽입
            if hasattr(table_info, "_vo_info"):
                # 딕셔너리를 재구성하여 access_files 다음에 vo_info 삽입
                # Python 3.7+에서는 딕셔너리가 삽입 순서를 유지함
                new_dict = {}
                for key, value in table_dict.items():
                    new_dict[key] = value
                    # access_files 다음에 vo_info 삽입
                    if key == "access_files":
                        new_dict["vo_info"] = table_info._vo_info
                table_dict = new_dict
            
            data_to_save.append(table_dict)

        persistence_manager.save_to_file(data_to_save, "table_access_info.json")
        logger.info(f"table_access_info.json 저장 완료 ({updated_count}개 항목 업데이트)")
    except Exception as e:
        logger.error(f"table_access_info.json 저장 실패: {e}")
        return 1

    logger.info("1단계 작업이 완료되었습니다.")
    
    # ========== 2단계: SQL 쿼리 분석 및 used_vo_info 생성 ==========
    logger.info("\n" + "=" * 60)
    logger.info("2단계: SQL 쿼리 분석 및 used_vo_info 생성 시작")
    logger.info("=" * 60)
    
    # table_access_info.json을 딕셔너리로 직접 로드 (vo_info 포함)
    try:
        table_access_info_data = persistence_manager.load_from_file(
            "table_access_info.json"
        )
        if not table_access_info_data:
            logger.warning("table_access_info.json에 데이터가 없습니다.")
            return 0

        logger.info(f"table_access_info.json 재로드 완료: {len(table_access_info_data)}개 항목")
    except Exception as e:
        logger.error(f"table_access_info.json 재로드 실패: {e}")
        return 1
    
    # 각 항목에 대해 SQL 쿼리 분석 수행
    step2_updated_count = 0
    for table_data in table_access_info_data:
        table_name = table_data.get("table_name", "")
        
        # vo_info 가져오기
        vo_info = table_data.get("vo_info", [])
        
        if not vo_info:
            logger.info(f"테이블 '{table_name}'에 대한 vo_info가 없습니다. 건너뜁니다.")
            continue
        
        # sql_queries 가져오기
        sql_queries = table_data.get("sql_queries", [])
        if not sql_queries:
            logger.info(f"테이블 '{table_name}'에 대한 sql_queries가 없습니다. 건너뜁니다.")
            continue
        
        logger.info(f"테이블 '{table_name}': {len(sql_queries)}개 SQL 쿼리 분석 시작")
        
        # 각 SQL 쿼리에 대해 분석 수행
        for sql_query_item in sql_queries:
            sql = sql_query_item.get("sql", "")
            if not sql:
                logger.warning(f"테이블 '{table_name}': SQL 쿼리가 비어있습니다. 건너뜁니다.")
                continue
            
            # SQL 쿼리 분석
            used_vo_info = analyze_sql_query(
                llm_provider, table_name, vo_info, sql
            )
            
            if not used_vo_info:
                logger.warning(f"테이블 '{table_name}': used_vo_info 생성 실패")
                continue
            
            # used_vo_info를 sql_query_item의 "call_stacks" 이전에 삽입
            # 딕셔너리를 재구성하여 call_stacks 이전에 used_vo_info 삽입
            new_sql_query_item = {}
            call_stacks_inserted = False
            
            for key, value in sql_query_item.items():
                # call_stacks 이전에 used_vo_info 삽입
                if key == "call_stacks" and not call_stacks_inserted:
                    new_sql_query_item["used_vo_info"] = used_vo_info
                    call_stacks_inserted = True
                new_sql_query_item[key] = value
            
            # call_stacks가 없는 경우 맨 끝에 추가
            if not call_stacks_inserted:
                new_sql_query_item["used_vo_info"] = used_vo_info
            
            # 원본 sql_query_item 업데이트
            sql_query_item.clear()
            sql_query_item.update(new_sql_query_item)
            
            logger.info(
                f"테이블 '{table_name}': SQL 쿼리 분석 완료 (used_vo_info {len(used_vo_info)}개 클래스)"
            )
        
        step2_updated_count += 1
    
    # 수정된 table_access_info.json 저장
    try:
        persistence_manager.save_to_file(table_access_info_data, "table_access_info.json")
        logger.info(f"table_access_info.json 저장 완료 (2단계: {step2_updated_count}개 항목 업데이트)")
    except Exception as e:
        logger.error(f"table_access_info.json 저장 실패: {e}")
        return 1

    logger.info("2단계 작업이 완료되었습니다.")
    
    # ========== 3단계: 코드 변경 계획 생성 ==========
    logger.info("\n" + "=" * 60)
    logger.info("3단계: 코드 변경 계획 생성 시작")
    logger.info("=" * 60)
    
    # CodeModifier 인스턴스 생성
    try:
        code_modifier = CodeModifier(config=config)
        logger.info("CodeModifier 인스턴스 생성 완료")
    except Exception as e:
        logger.error(f"CodeModifier 인스턴스 생성 실패: {e}")
        return 1
    
    # table_access_info.json 로드
    try:
        table_access_info_data = persistence_manager.load_from_file(
            "table_access_info.json"
        )
        if not table_access_info_data:
            logger.warning("table_access_info.json에 데이터가 없습니다.")
            return 0

        logger.info(f"table_access_info.json 로드 완료: {len(table_access_info_data)}개 항목")
    except Exception as e:
        logger.error(f"table_access_info.json 로드 실패: {e}")
        return 1
    
    # 각 테이블에 대해 코드 변경 계획 생성
    for table_data in table_access_info_data:
        table_name = table_data.get("table_name", "")
        
        # TableAccessInfo 객체로 변환
        try:
            table_info = TableAccessInfo.from_dict(table_data)
        except Exception as e:
            logger.error(f"테이블 '{table_name}': TableAccessInfo 변환 실패: {e}")
            continue
        
        logger.info(f"\n테이블 '{table_name}': 코드 변경 계획 생성 시작")
        
        # Contexts 생성
        try:
            contexts = code_modifier.generate_contexts(table_info)
            logger.info(f"테이블 '{table_name}': {len(contexts)}개 context 생성 완료")
        except Exception as e:
            logger.error(f"테이블 '{table_name}': Context 생성 실패: {e}")
            continue
        
        if not contexts:
            logger.info(f"테이블 '{table_name}': 생성된 context가 없습니다. 건너뜁니다.")
            continue
        
        # 각 context에 대해 코드 변경 계획 생성
        all_code_change_plans = []
        for context_idx, context in enumerate[ModificationContext](contexts):
            logger.info(
                f"테이블 '{table_name}': Context {context_idx + 1}/{len(contexts)} 처리 중"
            )
            
            try:
                code_change_plans = generate_code_change_plan(
                    code_modifier, context, table_info, table_data, target_project_path
                )
                all_code_change_plans.extend(code_change_plans)
            except Exception as e:
                logger.error(
                    f"테이블 '{table_name}': Context {context_idx + 1} 처리 실패: {e}"
                )
                continue
        
        # code_change_plan_{table_name}.json 파일 저장
        if all_code_change_plans:
            try:
                output_file = results_dir / f"code_change_plan_{table_name}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(all_code_change_plans, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"테이블 '{table_name}': 코드 변경 계획 저장 완료 ({len(all_code_change_plans)}개 항목) - {output_file}"
                )
            except Exception as e:
                logger.error(f"테이블 '{table_name}': 코드 변경 계획 저장 실패: {e}")
        else:
            logger.info(f"테이블 '{table_name}': 생성된 코드 변경 계획이 없습니다.")
    
    logger.info("모든 작업이 완료되었습니다.")
    return 0


def generate_code_change_plan(
    code_modifier: CodeModifier,
    context: ModificationContext,
    table_info: TableAccessInfo,
    table_data: Dict[str, Any],
    target_project_path: Path,
) -> List[Dict[str, Any]]:
    """
    코드 변경 계획을 생성합니다.

    Args:
        code_modifier: CodeModifier 인스턴스
        context: ModificationContext
        table_info: TableAccessInfo 객체
        table_data: 테이블 데이터 딕셔너리 (vo_info 등 포함)
        target_project_path: 타겟 프로젝트 경로

    Returns:
        코드 변경 계획 리스트
    """
    # 프롬프트 생성
    prompt = build_code_change_plan_prompt(
        code_modifier, context, table_info, table_data, target_project_path
    )
    
    # LLM 호출
    try:
        response = code_modifier.llm_provider.call(prompt)
        response_content = response.get("content", "")
        
        # JSON 응답 파싱
        code_change_plans = parse_code_change_plan_response(response_content)
        
        return code_change_plans
    except Exception as e:
        logger.error(f"LLM 호출 실패: {e}")
        return []


def build_code_change_plan_prompt(
    code_modifier: CodeModifier,
    context: ModificationContext,
    table_info: TableAccessInfo,
    table_data: Dict[str, Any],
    target_project_path: Path,
) -> str:
    """
    코드 변경 계획 생성을 위한 프롬프트를 구성합니다.

    Args:
        code_modifier: CodeModifier 인스턴스
        context: ModificationContext
        table_info: TableAccessInfo 객체
        table_data: 테이블 데이터 딕셔너리
        target_project_path: 타겟 프로젝트 경로

    Returns:
        생성된 프롬프트 문자열
    """
    # template_full.md 내용을 문자열 변수에 직접 복사
    template_str = """# Java Source Code Privacy Data Encryption Modification Point Identification Task

## Role and Objective
You are an expert Java developer specializing in Spring Framework applications. Your task is to identify modification points in Java source code where encryption/decryption calls should be added for personal information (주민번호/SSN, 성명/Name, 생년월일/Birth Date). **DO NOT modify the code directly. Instead, identify and report the modification points in JSON format.**

## Critical Requirements

### 1. Personal Information Column Recognition
Identify database columns and Java variables/properties/methods that handle personal information.
There are three types of informatioin that you have to recognize and handle.

**JUMIN Number (Social Security Number) type:**
- Column names patterns: JUMIN, SSN, JMN, RESID_NO, RRN, SOCIAL_SEC_NUM, JUM_NUM, etc.
- Variable names patterns: jumin, ssn, jmn, residNo, socialSecurityNumber, etc.

**Name type:**
- Column names pattern: NM, NAME, ACNM, CUST_NM, GVNM, INSRD_NM, USER_NAME, PERSON_NM, etc.
- Variable names patterns: name, nm, acnm, custNm, customerName, insuredName, etc.

**Birth Date type:**
- Column names patterns: BOD, DAY_OF_BIRTH, BIRTH_DATE, BIRTH_DAY, DOB, BRTH_DT, etc.
- Variable names patterns: bod, birthDate, dateOfBirth, birthDay, dob, etc.

**IMPORTANT:** Use semantic understanding to recognize variations. The column/variable name will contain hints about its purpose even if not exact matches.

### 2. Encryption/Decryption Logic Insertion Rules
** Encryption/Decryption methods:**
You have to use following methods to apply encryption or decryption.
- Encryption: k_sign.CryptoService.encrypt(input_value, policyNum, kSignValue)
- Decryption: k_sign.CryptoService.decrypt(input_value, policyNum, kSignValue)

You have to set policyNumber value depending on each type of the information :
- For JUMIN Number (Social Security Number) type : P10 (If other value is being used in existing code, that value should be changed to P10)
- For Name type : P20
- For Birth Date type : P30

You have to set kSignValue value depending on each type of the information :
- For JUMIN Number (Social Security Number) type : K_SIGN_JUMIN (If other value such like K_SIGN_SSN is being used in existing code, that value should be changed to K_SIGN_JUMIN)
- For Name type : K_SIGN_NAME
- For Birth Date type : K_SIGN_DOB

### 3. Modification Strategy
#### Types of modification
You have to identify modification points depending on each thpe of the information :

** For JUMIN Number (Social Security Number) type :**
- If you find existing encryption/description codes for this type, you just need to check and change policyNumber and kSignValue parameters as described in the above.
- You must not insert new encryption/description codes in this case.
-- Example 1: `dto.setJumin(k_sign.CryptoService.encrypt(ssn, P03, K_SIGN_SSN))` → `dto.setJumin(k_sign.CryptoService.encrypt(ssn, P10, K_SIGN_JUMIN))
-- Example 2: `ssn = k_sign.CryptoService.decrypt(dto.getJumin(), P03, K_SIGN_SSN))` → `ssn = k_sign.CryptoService.decrypt(dto.getJumin(), P10, K_SIGN_JUMIN))`

** For Name type :**
- For WRITE operations (DB INSERT/UPDATE), you have to apply encryption method BEFORE the value is assigned to DTO/Entity or passed to repository.
-- That could be done mainly with calling setters of DTO/DAO instances in the service layer. You have to decide the best way to do it by investigating existing codes.
-- Example: `dto.setName(name)` → `dto.setName(k_sign.CryptoService.encrypt(name, P20, K_SIGN_NAME))`

- For READ operations (DB SELECT): yoy have to apply decryption method AFTER the value is retrieved from DTO/Entity
-- That could be done mainly with calling getters of DTO/DAO instances in the service layer. You have to decide the best way to do it by investigating existing codes.
- Example: `String name = dto.getName()` → `String name = k_sign.CryptoService.decrypt(dto.getName(), P20, K_SIGN_NAME)`

** For Birth Date type :**
- For WRITE operations (DB INSERT/UPDATE), you have to apply encryption method BEFORE the value is assigned to DTO/Entity or passed to repository.
-- That could be done mainly with calling setters of DTO/DAO instances in the service layer. You have to decide the best way to do it by investigating existing codes.
-- Example: `dto.setDob(date)` → `dto.setDob(k_sign.CryptoService.encrypt(date, P30, K_SIGN_DOB))`

#### Modification Steps
Source code modification point identification must be approached through the following step-by-step process of thinking, execution, and verification:

1. Identify candidate codes.
First, you must identify candiate codes for change. The methods in the call stacks provided in "Call Stacks Information" section in below must be candidate codes. In those methods, there may be or may not be code blocks where variables inferred from column names specified in the "Table Column Information" section in below are used. For each selected candidate code, proceed with the identification work through steps 2-4 below.

2. Determin data flow type of the candidate codes.
Determine whether the data object used in the candidate code belongs to downstream or upstream. The process for making this determination is described in the sub-steps below.

2-1. The application is a backend application written in Java, and the framework can vary, including Spring, Anyframe, etc. The source code for each framework is divided into upper layer, middle layer, and lower layer. For example, as follows:

2-2. In the case of Spring framework, controller source files belong to the upper layer, service/service implementation belongs to the middle layer, and mapper or external interface source files belong to the lower layer. Among the lower layers, mapper is related to the database while external interface is not related to the database.

2-3. In the case of Anyframe framework, service/service implementation source files belong to the upper layer, business source files belong to the middle layer, and dem/dqm or external interface source files belong to the lower layer. Among the lower layers, dem/dqm is related to the database while external interface is not related to the database.

2-3. Downstream data flow means that data processing occurs as it is passed from top to bottom in the form of upper layer → middle layer → lower layer. In this case, the upper layer becomes the source layer and the lower layer becomes the destination layer. For example, if the data flow is downstream in Spring framework, the source layer is the controller and the destination layer is the mapper or external interface layer. Conversely, if it's upstream, the source layer is the mapper or external interface and the destination is the controller layer. The same approach applies to other frameworks. In Anyframe, if the data flow is downstream, the source layer is service/service implementation and the destination layer is dem/dqm or external interface. Conversely, if it's upstream, the source layer is dem/dqm or external interface layer and the destination layer is service/service implementation.

2-4. To determine whether the data flow processed in the candidate code belongs to downstream or upstream, you must identify the call relationships of the method containing the candidate code and verify the direction in which the data object is being passed. Perform this verification by comprehensively understanding the provided source code. Note that the method call relationships and data flow directions can differ.

Once the data flow of the candidate code is confirmed, identify the modification points according to the following steps:

3-1. If the data flow of the candidate code is downstream, determine whether the destination layer is a database-related layer. If it corresponds to this, identify modification points for encryption. If the destination layer is a layer unrelated to the database, no modifications should be made.

3-2. If the data flow of the candidate code is upstream, determine whether the source layer is a database-related layer. If it corresponds to this, identify modification points for decryption. If the source layer is a layer unrelated to the database, no modifications should be made.

3-3. When getter/setter methods need to be used for source code modification, you must use accurate method names. In order to do this, you have to examine provided DTO/DAO/VO class files.

4. Determine layers to change.
Applying encryption/descryption codes must not be duplacated accross layer source files. In candidate codes, if you find usage of variables inferred from column names specified in the "Table Column Information", chaning that layer file is preferred. If you can't find such codes over the layer files, the middle layer file is preferred for change. You can use each call stack provided in the "Call Stacks Information"

For example, in the case of Spring framework, the selection and modification of candidate code should be applied in either the controller layer or the service/service implementation layer, and should not occur redundantly in both layers. Similarly, in the case of Anyframe, it should be applied in either the service/service implementation layer or the business layer, and should not be applied redundantly in both layers.

5. Specify reason.
You must specify reason for code changeing or not chaning in the following format
- Object name of the data flow and its direction (upstream/downstream/both). Source layer (in case of upstream), destination layer (in case of downstream) in the provided call stack. Whethere the provided VO has properties for applying encryption/decryption and its name if it has.

**DO NOT modify:**

- Code unrelated to the specified tables and columns
- Controller layer (unless absolutely necessary)
- Repository layer (unless absolutely necessary)
- Import statements, class declarations, or method signatures
- Comments, logging statements, or validation logic


### 5. Output Requirements

**IMPORTANT:** Instead of modifying the code directly, you must identify the modification points and return them in JSON format. Do NOT modify the code, only identify where changes should be made.


### 6. Output Format Requirements

**⚠️⚠️⚠️ CRITICAL: OUTPUT FORMAT IS MANDATORY ⚠️⚠️⚠️**

**YOU MUST FOLLOW THIS EXACT OUTPUT FORMAT. NO EXCEPTIONS. NO OTHER TEXT OR COMMENTS ALLOWED.**

**OUTPUT FORMAT:**
You MUST return a JSON array where EACH input source file has ONE entry, even if there are no modification points for that file.

```json
[
  {
    "file_name": "<file name only, e.g., EmployeeService.java>",
    "change_points": [
      {
        "target_method": "<method name if modification is inside a method, 'import' if it's an import statement, 'class_property' if it's a class property>",
        "reason": "<For methods: follow the format in section 5. Specify reason. For others: brief explanation>",
        "location": "<For 'replace' type: the existing code block that needs to be replaced (the target code, NOT the new code). For 'insert' type: use format 'Insert before <code line>' where <code line> is the actual code line that comes AFTER the insertion point. For non-method cases: line number>",
        "change_type": "<'insert' for code addition, 'replace' for code replacement>",
        "enc_dec": "<'encryption' for encryption, 'decryption' for decryption>"
      }
    ]
  },
  {
    "file_name": "<another file name>",
    "change_points": []
  }
]
```

**CRITICAL RULES:**
1. **EVERY input source file MUST have an entry in the output array**, even if no modifications are needed.
2. **If a file has no modification points, set "change_points" to an empty array: []**
3. **Return ONLY the JSON array. NO other text, NO comments, NO explanations, NO markdown, NO code blocks. JUST THE RAW JSON ARRAY.**
4. **The JSON array must be valid JSON and parseable.**
5. **The "reason" field for methods must follow the format specified in section 5.**
6. **DO NOT generate any text before or after the JSON array.**
7. **DO NOT wrap the JSON in markdown code blocks or any other formatting.**
8. **DO NOT add any explanatory text, comments, or additional information.**

**EXAMPLE OUTPUT (for 2 input files, where first has changes and second has none):**

Example 1 - Insert type:
```json
[
  {
    "file_name": "EmployeeService.java",
    "change_points": [
      {
        "target_method": "saveUser",
        "reason": "Downstream data flow. Destination layer: mapper. VO has property 'name' for encryption.",
        "location": "Insert before userDao.insert(user);",
        "change_type": "insert",
        "enc_dec": "encryption"
      }
    ]
  },
  {
    "file_name": "EmployeeController.java",
    "change_points": []
  }
]
```

Example 2 - Replace type:
```json
[
  {
    "file_name": "EmployeeService.java",
    "change_points": [
      {
        "target_method": "saveUser",
        "reason": "Downstream data flow. Need to update existing encryption parameters.",
        "location": "user.setJumin(k_sign.CryptoService.encrypt(user.getJumin(), k_sign.CryptoService.P03, K_SIGN_SSN));",
        "change_type": "replace",
        "enc_dec": "encryption"
      }
    ]
  }
]
```

**IMPORTANT NOTES FOR LOCATION FIELD:**
- For "insert" type: Find the code line that comes AFTER where you want to insert, and use format "Insert before <that code line>"
- For "replace" type: Put the EXISTING code that needs to be replaced (the target code, NOT the replacement code)
- The location must be the actual code as it appears in the source file, not the modified version

**REMEMBER: OUTPUT ONLY THE JSON ARRAY. NOTHING ELSE.**

## Few-shot Examples

### Example 1: Service Layer - Save (Encrypt plain data columns)
**Before:**
```java
public void saveUser(User user) {
    userDao.insert(user);
}
```
**After (what should be identified):**
```java
public void saveUser(User user) {
    user.setName(k_sign.CryptoService.encrypt(user.getName(), k_sign.CryptoService.P20, K_SIGN_NAME));
    user.setDob(k_sign.CryptoService.encrypt(user.getDob(), k_sign.CryptoService.P30, K_SIGN_DOB));
    userDao.insert(user);
}
```
**Explanation:** Encrypt transformation for plain data columns before saving.

### Example 2: Service Layer - Retrieve (Decrypt plain data columns)
**Before:**
```java
public User getUserById(Long id) {
    User user = userDao.findById(id);
    return user;
}
```
**After (what should be identified):**
```java
public User getUserById(Long id) {
    User user = userDao.findById(id);
    if (user != null) {
        user.setName(k_sign.CryptoService.decrypt(user.getName(), k_sign.CryptoService.P20, K_SIGN_NAME));
        user.setDob(k_sign.CryptoService.decrypt(user.getDob(), k_sign.CryptoService.P30, K_SIGN_DOB));
    }
    return user;
}
```
**Explanation:** Decrypt encrypted plain data columns before returning after retrieval.

### Example 3: Service Layer - Save (Encrypt resident number column, change K_SIGN_SSN to K_SIGN_JUMIN)
**Before:**
```java
public void saveUser(User user) {
    user.setJumin(k_sign.CryptoService.encrypt(user.getJumin(), k_sign.CryptoService.P03, K_SIGN_SSN));
    userDao.insert(user);
}
```
**After (what should be identified):**
```java
public void saveUser(User user) {
    user.setJumin(k_sign.CryptoService.encrypt(user.getJumin(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
    userDao.insert(user);
}
```
**Explanation:** Change k_sign.CryptoService.P03 to k_sign.CryptoService.P10 and K_SIGN_SSN to K_SIGN_JUMIN.

### Example 4: Service Layer - Retrieve (Decrypt resident number column, change K_SIGN_SSN to K_SIGN_JUMIN)
**Before:**
```java
public User getUserById(Long id) {
    User user = userDao.findById(id);
    if (user != null) {
        user.setJumin(k_sign.CryptoService.decrypt(user.getJumin(), k_sign.CryptoService.P03, K_SIGN_SSN));
    }
    return user;
}
```
**After (what should be identified):**
```java
public User getUserById(Long id) {
    User user = userDao.findById(id);
    if (user != null) {
        user.setJumin(k_sign.CryptoService.decrypt(user.getJumin(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
    }
    return user;
}
```
**Explanation:** Change k_sign.CryptoService.P03 to k_sign.CryptoService.P10 and K_SIGN_SSN to K_SIGN_JUMIN.

From here, there are actual information and source codes that you have to handle
## Table Column Information
{{ table_info }}

## Source Files to Modify
{{ source_files }}

## Current Layer: {{ layer_name }}

## File Count: {{ file_count }}

## Call Stacks Information
The following call stacks show the method call relationships from the upper layer to lower layer methods. Methods of the upper and middle layer in each call stack should be candiate codes for applying encyption/decryption codes. You also have to use this information to understand the data flow direction when making modifications.
{{ call_stacks }}

## Warnings
1. Do not change the logic of existing code.
2. Only add encryption and decryption code.
3. The file_path must use the absolute path provided in source_files.
4. Do NOT perform any linting or formatting changes such as removing comments, trimming whitespace, or reformatting code. Only modify what is strictly necessary for encryption/decryption.
5. Do not remove or insert carrige return at the end of each source file. It should be as it is.

"""
    
    # 소스 파일 읽기
    source_files_snippets = []
    for file_path in context.file_paths:
        try:
            path_obj = Path(file_path)
            if not path_obj.is_absolute() and target_project_path:
                path_obj = target_project_path / file_path
            
            if path_obj.exists():
                with open(path_obj, "r", encoding="utf-8") as f:
                    content = f.read()
                source_files_snippets.append(f"=== File: {Path(file_path).name} ===\n{content}")
            else:
                logger.warning(f"파일을 찾을 수 없습니다: {path_obj}")
        except Exception as e:
            logger.warning(f"파일 읽기 실패: {file_path} - {e}")
    
    source_files_str = "\n\n".join(source_files_snippets)
    
    # 테이블 정보 JSON 형식으로 변환
    table_info_dict = {
        "table_name": table_info.table_name,
        "columns": table_info.columns,
    }
    table_info_str = json.dumps(table_info_dict, indent=2, ensure_ascii=False)
    
    # Call Stacks 정보 추출
    call_stacks_list = []
    used_vo_info_by_method = {}  # method_id -> used_vo_info
    
    for sql_query in table_info.sql_queries:
        query_id = sql_query.get("id", "")
        call_stacks = sql_query.get("call_stacks", [])
        used_vo_info = sql_query.get("used_vo_info", [])
        
        if call_stacks:
            call_stacks_list.extend(call_stacks)
            
            # query_id가 call_stack의 method name에 포함된 경우 used_vo_info 저장
            for call_stack in call_stacks:
                if isinstance(call_stack, list):
                    for method_sig in call_stack:
                        if isinstance(method_sig, str) and query_id in method_sig:
                            used_vo_info_by_method[query_id] = used_vo_info
                            break
    
    call_stacks_str = json.dumps(call_stacks_list, indent=2, ensure_ascii=False)
    
    # used_vo_info 정보 추가
    used_vo_info_sections = []
    for method_id, used_vo_info in used_vo_info_by_method.items():
        used_vo_info_json = json.dumps(used_vo_info, indent=2, ensure_ascii=False)
        used_vo_info_sections.append(
            f"==== Use following VO Information for method {method_id} =====\n{used_vo_info_json}"
        )
    
    used_vo_info_str = "\n\n".join(used_vo_info_sections)
    
    # used_vo_info가 있는 경우 Call Stacks Information 섹션 뒤에 추가
    if used_vo_info_str:
        # Call Stacks Information 섹션 뒤에 used_vo_info 추가
        template_str = template_str.replace(
            "{{ call_stacks }}",
            f"{{{{ call_stacks }}}}\n\n{used_vo_info_str}",
        )
    
    # 변수 치환
    variables = {
        "table_info": table_info_str,
        "source_files": source_files_str,
        "layer_name": context.layer,
        "file_count": context.file_count,
        "call_stacks": call_stacks_str,
    }
    
    # 템플릿 렌더링
    from modifier.code_generator.base_code_generator import render_template
    
    prompt = render_template(template_str, variables)
    
    return prompt


def parse_code_change_plan_response(response_content: str) -> List[Dict[str, Any]]:
    """
    LLM 응답에서 코드 변경 계획 JSON을 추출하고 파싱합니다.

    Args:
        response_content: LLM 응답 내용

    Returns:
        파싱된 코드 변경 계획 리스트
    """
    try:
        # JSON 코드 블록에서 JSON 추출 시도
        json_match = re.search(r"\[[\s\S]*\]", response_content)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        
        # 전체 내용을 JSON으로 파싱 시도
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 파싱 실패: {e}")
        logger.debug(f"응답 내용: {response_content}")
        # 빈 리스트 반환
        return []


if __name__ == "__main__":
    sys.exit(main())

