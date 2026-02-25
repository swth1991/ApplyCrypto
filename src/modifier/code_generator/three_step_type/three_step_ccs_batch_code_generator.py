"""
Three-Step CCS Batch Code Generator

CCS Batch 프로젝트 전용 ThreeStepBatchBaseCodeGenerator입니다.

특징:
- Phase 1: BAT.java + BATVO + XML 전체를 분석하여 데이터 흐름 기반 필드 매핑
- Phase 2: BAT.java + Phase 1 결과로 수정 지침 생성
- Phase 3: BAT.java만 수정 (SKIP 파일 필터링, ALL SKIP 최적화)

상속 구조:
    BaseMultiStepCodeGenerator
        └── ThreeStepCodeGenerator (기본 3단계 생성기)
            └── ThreeStepBatchBaseCodeGenerator (배치 공통 부모)
                └── ThreeStepCCSBatchCodeGenerator (CCS Batch 전용)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo

from .three_step_batch_base_code_generator import ThreeStepBatchBaseCodeGenerator

logger = logging.getLogger(__name__)


class ThreeStepCCSBatchCodeGenerator(ThreeStepBatchBaseCodeGenerator):
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

        logger.info(
            "ThreeStepCCSBatchCodeGenerator 초기화 완료 "
            "(BAT.java 데이터 흐름 분석 기반 필드 매핑 사용)"
        )

    # ========== 추상 메서드 구현 ==========

    def _get_batch_template_paths(self, template_dir: Path) -> Dict[str, Path]:
        """CCS Batch 전용 템플릿 경로를 반환합니다."""
        if self._is_name_only:
            logger.info(
                "ThreeStepCCSBatchCodeGenerator: name_only 모드 활성화 (이름 필드만 처리)"
            )
            return {
                "data_mapping": template_dir / "data_mapping_template_ccs_batch_name_only.md",
                "planning": template_dir / "planning_template_ccs_batch_name_only.md",
                "execution": template_dir / "execution_template_ccs_batch_name_only.md",
            }
        else:
            return {
                "data_mapping": template_dir / "data_mapping_template_ccs_batch.md",
                "planning": template_dir / "planning_template_ccs_batch.md",
                "execution": template_dir / "execution_template_ccs_batch.md",
            }

    def _create_batch_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """CCS Batch Phase 1 프롬프트 위임"""
        return self._create_ccs_batch_data_mapping_prompt(
            modification_context, table_access_info
        )

    def _create_batch_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> str:
        """CCS Batch Phase 2 프롬프트 위임"""
        return self._create_ccs_batch_planning_prompt(
            modification_context, table_access_info, mapping_info
        )

    # ========== CCS Batch 전용 프롬프트 생성 ==========

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
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        bat_source = self._read_file_contents(modification_context.file_paths)

        context_files = modification_context.context_files or []
        batvo_files = [f for f in context_files if f.lower().endswith(".java")]
        xml_files = [f for f in context_files if f.lower().endswith(".xml")]

        batvo_files_str = self._read_file_contents(batvo_files)

        sql_queries_str = self._get_sql_queries_for_prompt(
            table_access_info, modification_context.file_paths
        )

        xml_content_str = self._read_file_contents(xml_files) if xml_files else ""

        variables = {
            "table_info": table_info_str,
            "bat_source": bat_source,
            "batvo_files": batvo_files_str,
            "sql_queries": sql_queries_str,
            "xml_content": xml_content_str,
        }

        template_str = self._load_template(self._batch_data_mapping_template)
        return self._render_template(template_str, variables)

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
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        add_line_num = self.config and self.config.generate_type != "full_source"
        source_files_str = self._read_file_contents(
            modification_context.file_paths, add_line_num=add_line_num
        )

        mapping_info_str = json.dumps(mapping_info, indent=2, ensure_ascii=False)

        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "mapping_info": mapping_info_str,
            "dqm_java_info": "",  # CCS Batch는 BAT.java가 SQL id를 직접 참조하므로 DQM 불필요
        }

        template_str = self._load_template(self._batch_planning_template)
        return self._render_template(template_str, variables)
