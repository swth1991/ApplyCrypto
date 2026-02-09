"""
Three-Step Batch Base Code Generator

배치 프로젝트 공통 ThreeStep 코드 생성기 베이스 클래스입니다.
CCS Batch와 BNK Batch의 공통 로직을 추출하여 코드 중복을 제거합니다.

공통 로직:
    - _check_name_only_columns(): name_only 모드 판단
    - _enrich_mapping_info_with_target_metadata(): Phase 1 결과에 target 메타데이터 추가
    - _execute_data_mapping_phase(): Phase 1 실행 오케스트레이션
    - _execute_planning_phase(): Phase 2 실행 오케스트레이션
    - _format_instructions_for_execution(): Phase 2 → Phase 3 변환
    - _create_execution_prompt(): Phase 3 프롬프트 (SKIP 파일 필터링 포함)
    - _execute_execution_phase(): Phase 3 ALL SKIP 최적화

서브클래스 구현 필수:
    - _get_batch_template_paths(): 템플릿 경로 dict 반환
    - _create_batch_data_mapping_prompt(): Phase 1 프롬프트 생성
    - _create_batch_planning_prompt(): Phase 2 프롬프트 생성

상속 구조:
    BaseMultiStepCodeGenerator
        └── ThreeStepCodeGenerator (기본 3단계 생성기)
            └── ThreeStepBatchBaseCodeGenerator (배치 공통 부모)
                ├── ThreeStepCCSBatchCodeGenerator (CCS Batch 전용)
                └── ThreeStepBNKBatchCodeGenerator (BNK Batch 전용)
"""

import json
import logging
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo

from .three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")


class ThreeStepBatchBaseCodeGenerator(ThreeStepCodeGenerator):
    """
    배치 프로젝트 공통 3단계 LLM 협업 Code 생성기 베이스 클래스

    CCS Batch와 BNK Batch에서 공유하는 로직을 제공합니다.
    서브클래스는 _get_batch_template_paths(), _create_batch_data_mapping_prompt(),
    _create_batch_planning_prompt()를 구현해야 합니다.
    """

    def __init__(self, config):
        """
        ThreeStepBatchBaseCodeGenerator 초기화

        Args:
            config: 설정 객체 (three_step_config 필수)
        """
        super().__init__(config)

        # name_only 여부 판단
        self._is_name_only = self._check_name_only_columns()

        # 서브클래스가 제공하는 템플릿 경로
        template_dir = Path(__file__).parent
        paths = self._get_batch_template_paths(template_dir)
        self._batch_data_mapping_template = paths["data_mapping"]
        self._batch_planning_template = paths["planning"]
        self._batch_execution_template = paths["execution"]

        # 템플릿 존재 여부 확인
        for tmpl_name, tmpl_path in paths.items():
            if not tmpl_path.exists():
                raise FileNotFoundError(
                    f"템플릿을 찾을 수 없습니다: {tmpl_path}"
                )

    # ========== 서브클래스 구현 필수 ==========

    @abstractmethod
    def _get_batch_template_paths(self, template_dir: Path) -> Dict[str, Path]:
        """
        배치 전용 템플릿 경로를 반환합니다.

        Args:
            template_dir: 템플릿 디렉토리 경로

        Returns:
            Dict[str, Path]: {"data_mapping": Path, "planning": Path, "execution": Path}
        """
        pass

    @abstractmethod
    def _create_batch_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """Phase 1 프롬프트를 생성합니다. 서브클래스별 템플릿 변수 사용."""
        pass

    @abstractmethod
    def _create_batch_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> str:
        """Phase 2 프롬프트를 생성합니다. 서브클래스별 템플릿 변수 사용."""
        pass

    # ========== 공통 유틸리티 ==========

    def _check_name_only_columns(self) -> bool:
        """
        config의 access_tables에서 column_type이 모두 'name'인지 확인

        Returns:
            bool: name 타입만 있으면 True
        """
        if not self.config or not self.config.access_tables:
            return False

        for table in self.config.access_tables:
            for col in table.columns:
                if isinstance(col, str):
                    continue
                col_type = getattr(col, "column_type", "") or ""
                if col_type and col_type.lower() not in ("name", ""):
                    return False
        return True

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
            table_access_info: 테이블 접근 정보

        Returns:
            Dict[str, Any]: target metadata가 추가된 mapping_info
        """
        target_table = table_access_info.table_name
        target_columns = [col["name"] for col in table_access_info.columns]

        if "summary" not in mapping_info:
            mapping_info["summary"] = {}
        mapping_info["summary"]["target_table"] = target_table
        mapping_info["summary"]["target_columns"] = target_columns

        if "queries" in mapping_info:
            for query in mapping_info["queries"]:
                query["target_table"] = target_table
                query["target_columns"] = target_columns

        logger.debug(
            f"mapping_info에 target metadata 추가 완료: "
            f"table={target_table}, columns={target_columns}"
        )
        return mapping_info

    def _get_execution_template_path(self) -> Path:
        """배치 전용 Execution 템플릿 경로 반환"""
        return self._batch_execution_template

    # ========== Phase 1: Data Mapping (공통 오케스트레이션) ==========

    def _execute_data_mapping_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Phase 1: BAT.java + BATVO + XML 기반 데이터 매핑 분석 (공통 오케스트레이션)

        서브클래스의 _create_batch_data_mapping_prompt()를 호출하여
        프롬프트를 생성하고, LLM 호출 및 결과 처리를 수행합니다.
        """
        logger.info("-" * 40)
        logger.info("[Step 1] Query Analysis 시작 (Batch: 데이터 흐름 분석)...")
        logger.info(f"BAT 파일 수: {len(modification_context.file_paths)}")
        logger.info(f"Context 파일 수: {len(modification_context.context_files or [])}")

        # 서브클래스 전용 프롬프트 생성
        prompt = self._create_batch_data_mapping_prompt(
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

        # target metadata 추가
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

        query_count = len(mapping_info.get("queries", []))
        logger.info(f"Query Analysis 완료: {query_count}개 쿼리")

        return mapping_info, tokens_used

    # ========== Phase 2: Planning (공통 오케스트레이션) ==========

    def _execute_planning_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """
        Phase 2: BAT.java 수정 지침 생성 (공통 오케스트레이션)

        서브클래스의 _create_batch_planning_prompt()를 호출하여
        프롬프트를 생성하고, LLM 호출 및 결과 처리를 수행합니다.
        """
        logger.info("-" * 40)
        logger.info("[Step 2] Planning 시작 (Batch)...")
        logger.info(f"BAT 파일 수: {len(modification_context.file_paths)}")

        # 서브클래스 전용 프롬프트 생성
        prompt = self._create_batch_planning_prompt(
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

    # ========== Phase 3 헬퍼: Instruction 포맷 변환 ==========

    def _format_instructions_for_execution(
        self,
        instructions: List[Dict[str, Any]],
    ) -> str:
        """
        Phase 2의 modification_instructions를 Phase 3용 가독성 좋은 마크다운 형태로 변환합니다.

        Args:
            instructions: Phase 2에서 생성된 modification_instructions 리스트

        Returns:
            str: 마크다운 형태로 변환된 수정 지침
        """
        if not instructions:
            return "No modification instructions provided."

        output_parts = []
        output_parts.append("## Modification Instructions\n")
        output_parts.append(f"**Total: {len(instructions)} modification(s)**\n")

        for idx, inst in enumerate(instructions, 1):
            action = inst.get("action", "UNKNOWN")
            file_name = inst.get("file_name", "Unknown")
            target_method = inst.get("target_method", "Unknown")

            output_parts.append(f"### Modification {idx}: {action}")
            output_parts.append("")

            output_parts.append("| Field | Value |")
            output_parts.append("|-------|-------|")

            if action == "SKIP":
                reason = inst.get("reason", "No reason provided")
                output_parts.append(f"| Action | **{action}** |")
                output_parts.append(f"| Reason | {reason} |")
                output_parts.append("")
                output_parts.append("**→ No code modification needed.**")
                output_parts.append("")
            else:
                target_properties = inst.get("target_properties", [])
                insertion_point = inst.get("insertion_point", "Not specified")
                code_pattern_hint = inst.get("code_pattern_hint", "")
                reason = inst.get("reason", "")

                output_parts.append(f"| File | `{file_name}` |")
                output_parts.append(f"| Method | `{target_method}` |")
                output_parts.append(f"| Action | **{action}** |")
                props_str = (
                    ", ".join(target_properties) if target_properties else "None"
                )
                output_parts.append(f"| Target Properties | `{props_str}` |")
                output_parts.append(f"| Insertion Point | {insertion_point} |")
                if reason:
                    output_parts.append(f"| Reason | {reason} |")
                output_parts.append("")

                if code_pattern_hint:
                    output_parts.append("**Code to Insert:**")
                    output_parts.append("")
                    output_parts.append("```java")
                    output_parts.append(code_pattern_hint)
                    output_parts.append("```")

                output_parts.append("")

            output_parts.append("---")
            output_parts.append("")

        return "\n".join(output_parts)

    # ========== Phase 3 오버라이드: 파일 필터링 + SKIP 최적화 ==========

    def _create_execution_prompt(
        self,
        modification_context: ModificationContext,
        modification_instructions: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[int, str], Dict[str, str], Dict[str, str]]:
        """
        Execution 프롬프트를 생성합니다. SKIP이 아닌 파일만 포함합니다.

        Returns:
            Tuple[str, Dict[int, str], Dict[str, str], Dict[str, str]]:
                - Execution 프롬프트
                - 인덱스 -> 파일 경로 매핑
                - 파일명 -> 파일 경로 매핑
                - 파일 경로 -> 파일 내용 매핑
        """
        add_line_num = self.config and self.config.generate_type != "full_source"

        # modification_instructions에서 SKIP이 아닌 파일들만 추출
        target_file_names = {
            inst.get("file_name")
            for inst in modification_instructions
            if inst.get("action") != "SKIP" and inst.get("file_name")
        }

        # 전체 파일 경로에서 대상 파일만 필터링
        if target_file_names:
            filtered_file_paths = [
                fp
                for fp in modification_context.file_paths
                if Path(fp).name in target_file_names
            ]
        else:
            filtered_file_paths = []

        logger.info(
            f"Phase 3 소스 파일 필터링: "
            f"{len(modification_context.file_paths)}개 → {len(filtered_file_paths)}개"
        )

        # 필터링된 파일만 읽기
        source_files_str, index_to_path, path_to_content = (
            self._read_file_contents_indexed(
                filtered_file_paths, add_line_num=add_line_num
            )
        )

        # 파일명 -> 파일 경로 매핑 생성
        file_mapping = {Path(fp).name: fp for fp in filtered_file_paths}

        # 수정 지침을 마크다운 형태로 변환
        instructions_str = self._format_instructions_for_execution(
            modification_instructions
        )

        # 템플릿 변수 준비
        variables = {
            "source_files": source_files_str,
            "modification_instructions": instructions_str,
        }

        template_str = self._load_template(self._batch_execution_template)
        prompt = self._render_template(template_str, variables)

        return prompt, index_to_path, file_mapping, path_to_content

    def _execute_execution_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        modification_instructions: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Execution phase를 실행합니다. (배치 공통 오버라이드)

        모든 instruction이 SKIP인 경우 LLM 호출을 건너뛰고 빈 결과를 반환합니다.

        Args:
            session_dir: 세션 디렉토리 경로
            modification_context: 수정 컨텍스트
            modification_instructions: 수정 지침 리스트

        Returns:
            Tuple[List[Dict[str, Any]], int]: (파싱된 수정 정보 리스트, 사용된 토큰 수)
        """
        all_skip = all(
            inst.get("action") == "SKIP" for inst in modification_instructions
        )

        if all_skip:
            logger.info("-" * 40)
            logger.info(
                "[Execution Phase] 모든 instruction이 SKIP - LLM 호출 건너뜀"
            )
            logger.info(f"SKIP된 instruction 수: {len(modification_instructions)}개")
            return [], 0

        # SKIP이 아닌 instruction이 있으면 부모 클래스 메서드 호출
        return super()._execute_execution_phase(
            session_dir, modification_context, modification_instructions
        )
