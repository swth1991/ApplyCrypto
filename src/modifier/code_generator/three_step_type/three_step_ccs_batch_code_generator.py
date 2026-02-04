"""
Three-Step CCS Batch Code Generator

CCS Batch 프로젝트 전용 ThreeStepCodeGenerator입니다.

특징:
- Phase 1: BAT.java + BATVO + XML 전체를 분석하여 데이터 흐름 기반 필드 매핑
- Phase 2: BAT.java + Phase 1 결과로 수정 지침 생성
- Phase 3: BAT.java만 수정

상속 구조:
    BaseMultiStepCodeGenerator
        └── ThreeStepCodeGenerator (기본 3단계 생성기)
            └── ThreeStepCCSBatchCodeGenerator (CCS Batch 전용)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo

from .three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")


class ThreeStepCCSBatchCodeGenerator(ThreeStepCodeGenerator):
    """
    CCS Batch 전용 3단계 LLM 협업 Code 생성기

    Phase 1에서 BAT.java 코드의 데이터 흐름을 분석하여
    SQL ID ↔ VO 클래스 ↔ 필드 매핑을 추론합니다.

    기존 CCS와의 차이점:
    - DQM.xml의 resultMap 대신 BAT.java + BATVO + SQL 쿼리 분석
    - itemFactory.getItemReader("sqlId", VO.class) 패턴 기반 매핑
    - vo.getXxx() / vo.setXxx() 패턴에서 실제 사용 필드 식별
    """

    def __init__(self, config):
        """
        ThreeStepCCSBatchCodeGenerator 초기화

        Args:
            config: 설정 객체 (three_step_config 필수)
        """
        super().__init__(config)

        # CCS Batch 전용 템플릿 경로 설정
        template_dir = Path(__file__).parent

        # name_only 여부 판단
        self._is_name_only = self._check_name_only_columns()

        if self._is_name_only:
            self.data_mapping_template_ccs_batch_path = (
                template_dir / "data_mapping_template_ccs_batch_name_only.md"
            )
            self.planning_template_ccs_batch_path = (
                template_dir / "planning_template_ccs_batch_name_only.md"
            )
            self.execution_template_ccs_batch_path = (
                template_dir / "execution_template_ccs_batch_name_only.md"
            )
            logger.info(
                "ThreeStepCCSBatchCodeGenerator: name_only 모드 활성화 (이름 필드만 처리)"
            )
        else:
            self.data_mapping_template_ccs_batch_path = (
                template_dir / "data_mapping_template_ccs_batch.md"
            )
            self.planning_template_ccs_batch_path = (
                template_dir / "planning_template_ccs_batch.md"
            )
            self.execution_template_ccs_batch_path = (
                template_dir / "execution_template_ccs_batch.md"
            )

        # 템플릿 존재 여부 확인
        for template in [
            self.data_mapping_template_ccs_batch_path,
            self.planning_template_ccs_batch_path,
            self.execution_template_ccs_batch_path,
        ]:
            if not template.exists():
                raise FileNotFoundError(f"템플릿을 찾을 수 없습니다: {template}")

        logger.info(
            "ThreeStepCCSBatchCodeGenerator 초기화 완료 "
            "(BAT.java 데이터 흐름 분석 기반 필드 매핑 사용)"
        )

    def _check_name_only_columns(self) -> bool:
        """
        config의 access_tables에서 column_type이 모두 'name'인지 확인

        Returns:
            bool: name 타입만 있으면 True
        """
        if not self.config or not self.config.access_tables:
            return False

        for table in self.config.access_tables:
            for col in table.get("columns", []):
                col_type = col.get("column_type", "")
                if col_type and col_type.lower() not in ("name", ""):
                    return False
        return True

    def _get_execution_template_path(self) -> Path:
        """CCS Batch 전용 Execution 템플릿 경로 반환"""
        return self.execution_template_ccs_batch_path

    # ========== Phase 1 오버라이드: CCS Batch 전용 Data Mapping ==========

    def _execute_data_mapping_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Phase 1: BAT.java + BATVO + XML 기반 데이터 매핑 분석

        기존 CCS와 차이점:
        - BAT.java 코드도 포함하여 데이터 흐름 분석
        - itemFactory.getItemReader("sqlId", VO.class) 패턴 분석
        - vo.getXxx() / vo.setXxx() 패턴에서 실제 사용 필드 식별
        """
        logger.info("-" * 40)
        logger.info("[Step 1] Query Analysis 시작 (CCS Batch: 데이터 흐름 분석)...")
        logger.info(f"BAT 파일 수: {len(modification_context.file_paths)}")
        logger.info(f"Context 파일 수: {len(modification_context.context_files or [])}")

        # CCS Batch 전용 프롬프트 생성
        prompt = self._create_ccs_batch_data_mapping_prompt(
            modification_context, table_access_info
        )

        logger.debug(f"Query Analysis 프롬프트 길이: {len(prompt)} chars")

        # 프롬프트 저장
        self._save_prompt_to_file(prompt, modification_context, "data_mapping")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Query Analysis 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱
        mapping_info = self._parse_json_response(response, "Query Analysis")

        # mapping_info의 각 쿼리에 target_table 및 target_columns 메타데이터 추가
        # Phase 2에서 target table 접근 여부를 재평가하지 않도록 명시적 정보 제공
        mapping_info = self._enrich_mapping_info_with_target_metadata(
            mapping_info, table_access_info
        )

        # 결과 저장
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=1,
            phase_name="query_analysis",
            result=mapping_info,
            tokens_used=tokens_used,
        )

        # 요약 로깅
        query_count = len(mapping_info.get("queries", []))
        logger.info(f"Query Analysis 완료: {query_count}개 쿼리")

        return mapping_info, tokens_used

    def _enrich_mapping_info_with_target_metadata(
        self,
        mapping_info: Dict[str, Any],
        table_access_info: TableAccessInfo,
    ) -> Dict[str, Any]:
        """
        mapping_info의 각 쿼리에 target_table 및 target_columns 정보를 추가합니다.

        Phase 2 LLM이 target table 접근 여부를 재평가하지 않도록
        Phase 1에서 검증된 정보를 명시적으로 포함시킵니다.

        Args:
            mapping_info: Phase 1에서 파싱된 쿼리 분석 결과
            table_access_info: 테이블 접근 정보 (target table/columns 포함)

        Returns:
            Dict[str, Any]: target metadata가 추가된 mapping_info
        """
        target_table = table_access_info.table_name
        target_columns = [col["name"] for col in table_access_info.columns]

        # summary에 target 정보 추가
        if "summary" not in mapping_info:
            mapping_info["summary"] = {}
        mapping_info["summary"]["target_table"] = target_table
        mapping_info["summary"]["target_columns"] = target_columns

        # 각 쿼리에도 target 정보 추가 (Phase 2에서 명확하게 인식할 수 있도록)
        if "queries" in mapping_info:
            for query in mapping_info["queries"]:
                query["target_table"] = target_table
                query["target_columns"] = target_columns

        logger.debug(
            f"mapping_info에 target metadata 추가 완료: "
            f"table={target_table}, columns={target_columns}"
        )
        return mapping_info

    def _create_ccs_batch_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """
        CCS Batch 전용 Phase 1 프롬프트 생성

        템플릿 변수:
        - table_info: 암호화 대상 테이블/컬럼
        - bat_source: BAT.java 소스 코드
        - batvo_files: BATVO 파일 내용들
        - sql_queries: XXX_SQL.xml에서 추출한 쿼리
        - xml_content: XML 파일 원본 (참조용)
        """
        # 테이블/컬럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # BAT.java 소스 코드 (file_paths에서)
        bat_source = self._read_file_contents(modification_context.file_paths)

        # context_files에서 BATVO와 XML 분리
        context_files = modification_context.context_files or []
        batvo_files = [f for f in context_files if f.lower().endswith(".java")]
        xml_files = [f for f in context_files if f.lower().endswith(".xml")]

        # BATVO 파일 내용
        batvo_files_str = self._read_file_contents(batvo_files)

        # SQL 쿼리 (table_access_info에서)
        sql_queries_str = self._get_sql_queries_for_prompt(
            table_access_info, modification_context.file_paths
        )

        # XML 파일도 직접 포함 (SQL 외 추가 정보용)
        xml_content_str = self._read_file_contents(xml_files) if xml_files else ""

        variables = {
            "table_info": table_info_str,
            "bat_source": bat_source,
            "batvo_files": batvo_files_str,
            "sql_queries": sql_queries_str,
            "xml_content": xml_content_str,
        }

        template_str = self._load_template(self.data_mapping_template_ccs_batch_path)
        return self._render_template(template_str, variables)

    # ========== Phase 2 오버라이드: CCS Batch 전용 Planning ==========

    def _execute_planning_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """
        Phase 2: BAT.java 수정 지침 생성

        입력: BAT.java + Phase 1 결과(mapping_info)
        출력: data_flow_analysis + modification_instructions

        Note: CCS Batch는 call_stacks가 없음 (BAT가 최상위 실행 단위)
        """
        logger.info("-" * 40)
        logger.info("[Step 2] Planning 시작 (CCS Batch)...")
        logger.info(f"BAT 파일 수: {len(modification_context.file_paths)}")

        # CCS Batch 전용 프롬프트 생성
        prompt = self._create_ccs_batch_planning_prompt(
            modification_context, table_access_info, mapping_info
        )

        logger.debug(f"Planning 프롬프트 길이: {len(prompt)} chars")

        # 프롬프트 저장
        self._save_prompt_to_file(prompt, modification_context, "planning")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Planning 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱
        modification_instructions = self._parse_json_response(response, "Planning")

        # 결과 저장
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=2,
            phase_name="planning",
            result=modification_instructions,
            tokens_used=tokens_used,
        )

        instruction_count = len(
            modification_instructions.get("modification_instructions", [])
        )
        logger.info(f"생성된 수정 지침 수: {instruction_count}")

        return modification_instructions, tokens_used

    def _create_ccs_batch_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> str:
        """
        CCS Batch 전용 Phase 2 프롬프트 생성

        템플릿 변수:
        - table_info: 암호화 대상 테이블/컬럼
        - source_files: BAT.java 소스 코드 (줄번호 포함)
        - mapping_info: Phase 1 결과 (JSON)

        Note: call_stacks는 포함하지 않음 (CCS Batch는 BAT가 최상위)
        """
        # 테이블/컬럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # BAT.java 소스 파일 (줄번호 추가 여부)
        add_line_num = self.config and self.config.generate_type != "full_source"
        source_files_str = self._read_file_contents(
            modification_context.file_paths, add_line_num=add_line_num
        )

        # mapping_info를 JSON 문자열로
        mapping_info_str = json.dumps(mapping_info, indent=2, ensure_ascii=False)

        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "mapping_info": mapping_info_str,
            "dqm_java_info": "",  # CCS Batch는 BAT.java가 SQL id를 직접 참조하므로 DQM 불필요
        }

        template_str = self._load_template(self.planning_template_ccs_batch_path)
        return self._render_template(template_str, variables)
