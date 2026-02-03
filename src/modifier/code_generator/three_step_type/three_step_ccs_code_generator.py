"""
Three-Step CCS Code Generator

CCS(AnyframeCCS) 프레임워크 전용 ThreeStepCodeGenerator입니다.

CCS 프로젝트의 특징:
- DQM.xml 파일의 resultMap 태그에 컬럼↔필드 매핑 정보가 명시되어 있음
- VO 파일 전체를 포함하지 않고, resultMap 매핑 정보만 추출하여 사용
- Phase 1 프롬프트 토큰 70-90% 절약

상속 구조:
    BaseMultiStepCodeGenerator
        └── ThreeStepCodeGenerator (기본 3단계 생성기)
            └── ThreeStepCCSCodeGenerator (CCS 전용)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo

from .three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")

# CCS prefix별 유틸리티 클래스 매핑
# package_prefix: sli.ccs.{prefix}.svcutil 형태의 import 경로에 사용
CCS_UTIL_MAPPING: Dict[str, Dict[str, str]] = {
    "BC": {
        "common_util": "BCCommonUtil",
        "masking_util": "BCMaskingUtil",
        "package_prefix": "bc",
    },
    "CP": {
        "common_util": "CPCmpgnUtil",
        "masking_util": "CPMaskingUtil",
        "package_prefix": "cp",
    },
    "CR": {
        "common_util": "CRCommonUtil",
        "masking_util": "CRMaskingUtil",
        "package_prefix": "cr",
    },
}


class ThreeStepCCSCodeGenerator(ThreeStepCodeGenerator):
    """
    CCS(AnyframeCCS) 프레임워크 전용 3단계 LLM 협업 Code 생성기

    Phase 1에서 VO 파일 전체 대신 DQM.xml의 resultMap 필드 매핑을 사용합니다.
    Phase 2, 3는 기본 ThreeStepCodeGenerator와 동일합니다.
    """

    def __init__(self, config):
        """
        ThreeStepCCSCodeGenerator 초기화

        Args:
            config: 설정 객체 (three_step_config 필수)
        """
        super().__init__(config)

        # CCS 유틸리티 정보 초기화
        self.ccs_util_info = self._get_ccs_util_info()

        # CCS 전용 템플릿 경로 설정
        template_dir = Path(__file__).parent
        self.data_mapping_template_ccs_path = (
            template_dir / "data_mapping_template_ccs.md"
        )
        self.planning_template_ccs_path = (
            template_dir / "planning_template_ccs.md"
        )
        self.execution_template_ccs_path = (
            template_dir / "execution_template_ccs.md"
        )

        # CCS 템플릿 존재 여부 확인
        required_templates = [
            self.data_mapping_template_ccs_path,
            self.planning_template_ccs_path,
            self.execution_template_ccs_path,
        ]
        for template_path in required_templates:
            if not template_path.exists():
                raise FileNotFoundError(
                    f"CCS 템플릿을 찾을 수 없습니다: {template_path}"
                )

        # 로깅
        if self.ccs_util_info:
            logger.info(
                f"ThreeStepCCSCodeGenerator 초기화 완료 "
                f"(ccs_prefix: {config.ccs_prefix}, "
                f"common_util: {self.ccs_util_info.get('common_util')})"
            )
        else:
            logger.info(
                "ThreeStepCCSCodeGenerator 초기화 완료 "
                "(ccs_prefix 미설정, 기존 패턴 사용)"
            )

    # ========== CCS 유틸리티 정보 관리 ==========

    def _get_ccs_util_info(self) -> Dict[str, str]:
        """
        CCS prefix 기반 유틸리티 클래스 정보를 반환합니다.

        Returns:
            Dict[str, str]: common_util, masking_util 키를 가진 딕셔너리.
                            ccs_prefix가 설정되지 않은 경우 빈 딕셔너리 반환.
        """
        ccs_prefix = getattr(self.config, "ccs_prefix", None)
        if ccs_prefix and ccs_prefix in CCS_UTIL_MAPPING:
            return CCS_UTIL_MAPPING[ccs_prefix]
        return {}

    def _format_ccs_util_info_for_prompt(self) -> str:
        """
        프롬프트용 CCS 유틸리티 정보를 포맷팅합니다.

        Returns:
            str: 템플릿에 삽입될 유틸리티 정보 문자열
        """
        if not self.ccs_util_info:
            return "CCS prefix not configured. Using standard SliEncryptionUtil patterns."

        common_util = self.ccs_util_info.get("common_util", "N/A")
        masking_util = self.ccs_util_info.get("masking_util", "N/A")
        return f"""- **Common Utility**: `{common_util}`
- **Masking Utility**: `{masking_util}`"""

    # ========== Phase 1 오버라이드: CCS 전용 Data Mapping ==========

    def _execute_data_mapping_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Step 1 (Query Analysis): CCS용 resultMap 기반 데이터 매핑 정보를 추출합니다.

        VO 파일 전체 대신 DQM.xml에서 추출한 필드 매핑 정보를 사용하여
        토큰을 대폭 절약합니다.
        """
        logger.info("-" * 40)
        logger.info("[Step 1] Query Analysis 시작 (CCS: resultMap 기반)...")

        # CCS 전용 프롬프트 생성
        prompt = self._create_ccs_data_mapping_prompt(
            modification_context, table_access_info
        )

        logger.debug(f"Query Analysis 프롬프트 길이: {len(prompt)} chars")

        # 프롬프트 저장 (LLM 호출 직전)
        self._save_prompt_to_file(prompt, modification_context, "data_mapping")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Query Analysis 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱 (부모 클래스의 범용 메서드 사용)
        mapping_info = self._parse_json_response(response, "Query Analysis")

        # 결과 저장
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=1,
            phase_name="query_analysis",
            result=mapping_info,
            tokens_used=tokens_used,
        )

        return mapping_info, tokens_used

    # ========== CCS 전용 헬퍼 메서드 ==========

    def _create_ccs_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """
        CCS 전용 Phase 1 프롬프트를 생성합니다.

        VO 파일 전체 대신 DQM.xml에서 추출한 필드 매핑 정보를
        각 SQL 쿼리와 함께 컴팩트하게 제공합니다.

        Args:
            modification_context: 수정 컨텍스트
            table_access_info: 테이블 접근 정보

        Returns:
            str: 렌더링된 프롬프트
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # target columns 추출 (관심 대상 컬럼명 리스트)
        target_columns = [col.get("name", "") for col in modification_context.columns]

        # SQL 쿼리 + 관련 필드 매핑을 함께 포맷팅 (중복 제거, 컴팩트화)
        sql_queries_with_mappings = self._format_ccs_sql_with_relevant_mappings(
            table_access_info, modification_context.file_paths, target_columns
        )

        variables = {
            "table_info": table_info_str,
            "sql_queries_with_mappings": sql_queries_with_mappings,
        }

        template_str = self._load_template(self.data_mapping_template_ccs_path)
        return self._render_template(template_str, variables)

    def _format_ccs_sql_with_relevant_mappings(
        self,
        table_access_info: TableAccessInfo,
        file_paths: list,
        target_columns: list,
    ) -> str:
        """
        CCS용 SQL 쿼리와 관련 필드 매핑을 함께 포맷팅합니다.

        각 쿼리 밑에 target_columns에 해당하는 필드 매핑만 자연어로 설명합니다.

        Args:
            table_access_info: 테이블 접근 정보
            file_paths: 파일 경로 리스트 (필터링용)
            target_columns: 관심 대상 컬럼명 리스트

        Returns:
            str: 포맷팅된 SQL 쿼리 + 매핑 정보 문자열
        """
        # target_columns를 대문자로 정규화 (비교용)
        target_cols_upper = {col.upper() for col in target_columns}

        # 파일 경로에서 클래스명 추출 (필터링용)
        file_class_names = set()
        if file_paths:
            for file_path in file_paths:
                class_name = Path(file_path).stem
                file_class_names.add(class_name)

        output_parts = []
        query_num = 0

        for sql_query in table_access_info.sql_queries:
            # 파일 경로가 지정된 경우 관련 SQL만 필터링
            if file_paths and file_class_names:
                call_stacks = sql_query.get("call_stacks", [])
                is_relevant = False
                for call_stack in call_stacks:
                    if not isinstance(call_stack, list):
                        continue
                    for method_sig in call_stack:
                        if not isinstance(method_sig, str):
                            continue
                        method_class_name = (
                            method_sig.split(".")[0] if "." in method_sig else method_sig
                        )
                        if method_class_name in file_class_names:
                            is_relevant = True
                            break
                    if is_relevant:
                        break
                if not is_relevant:
                    continue

            query_num += 1
            query_id = sql_query.get("id", "unknown")
            query_type = sql_query.get("query_type", "SELECT")
            sql_text = sql_query.get("sql", "")
            strategy_specific = sql_query.get("strategy_specific", {})

            # 쿼리 헤더
            output_parts.append(f"### Query {query_num}: {query_id} ({query_type})")
            output_parts.append("")

            # SQL 텍스트 (strategy_specific 제외한 간결한 형태)
            output_parts.append("**SQL:**")
            output_parts.append("```sql")
            output_parts.append(sql_text.strip())
            output_parts.append("```")
            output_parts.append("")

            # 메타 정보
            param_type = strategy_specific.get("parameter_type", "")
            result_type = strategy_specific.get("result_type", "")
            if param_type:
                output_parts.append(f"- **Parameter Type:** `{param_type}`")
            if result_type:
                output_parts.append(f"- **Result Type:** `{result_type}`")
            output_parts.append("")

            # 관련 필드 매핑 (target_columns만 필터링)
            relevant_mappings = []

            if query_type == "SELECT":
                # resultMap에서 추출한 필드 매핑
                result_field_mappings = strategy_specific.get(
                    "result_field_mappings", []
                )
                for java_field, db_column in result_field_mappings:
                    if db_column.upper() in target_cols_upper:
                        relevant_mappings.append(
                            f"- Column `{db_column}` → Java field `{java_field}`"
                        )

            elif query_type in ("INSERT", "UPDATE"):
                # SQL 내 #{fieldName} 패턴
                param_fields = strategy_specific.get("parameter_field_mappings", [])
                # INSERT/UPDATE는 SQL에서 컬럼명을 직접 추출해야 함
                # 여기서는 parameter_fields만 제공하고, 컬럼 매칭은 LLM에게 위임
                if param_fields:
                    # 간단히 모든 파라미터 필드 나열 (LLM이 컬럼과 매칭)
                    for field in param_fields:
                        relevant_mappings.append(
                            f"- Parameter `#{{{field}}}` → Java field `{field}`"
                        )

            if relevant_mappings:
                output_parts.append(
                    f"**Relevant Field Mappings for Target Columns ({', '.join(target_columns)}):**"
                )
                output_parts.extend(relevant_mappings)
            else:
                output_parts.append(
                    "**Field Mappings:** No direct mapping found for target columns. "
                    "Infer from SQL parameter names or use camelCase conversion."
                )

            output_parts.append("")
            output_parts.append("---")
            output_parts.append("")

        if query_num == 0:
            return "No relevant SQL queries found for this context."

        logger.info(f"CCS SQL 쿼리 포맷팅 완료: {query_num}개 쿼리")
        return "\n".join(output_parts)

    # ========== DQM.java 정보 추출 (Phase 2용) ==========

    def _extract_dqm_java_info(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """
        현재 컨텍스트에서 실제로 import하는 DQM.java 파일만 찾아 전체 내용을 반환합니다.

        CCS 프로젝트에서 XML query id와 Java 메서드 간의 연결 정보를 제공하기 위해
        DQM.java 파일 내용을 Planning 프롬프트에 포함시킵니다.

        Args:
            modification_context: 수정 컨텍스트 (CTL, SVCImpl 파일 경로 포함)
            table_access_info: 테이블 접근 정보 (layer_files 포함)

        Returns:
            str: 관련 DQM.java 파일들의 전체 내용 (없으면 빈 문자열)
        """
        # Step 1: CTL, SVCImpl 파일에서 import된 DQM 클래스명 추출
        imported_dqm_classes = set()
        for file_path in modification_context.file_paths:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
                for line in content.split("\n"):
                    line = line.strip()
                    # import 문에서 DQM 클래스 추출
                    # 예: import com.example.dqm.UserDQM;
                    if line.startswith("import ") and "DQM" in line:
                        # 세미콜론 제거 후 마지막 부분(클래스명) 추출
                        class_part = line.replace(";", "").split(".")[-1].strip()
                        if class_part.upper().endswith("DQM"):
                            imported_dqm_classes.add(class_part)
            except Exception as e:
                logger.warning(f"DQM import 추출 실패: {file_path} - {e}")
                continue

        if not imported_dqm_classes:
            logger.debug("import된 DQM 클래스가 없습니다.")
            return ""

        logger.info(f"import된 DQM 클래스: {imported_dqm_classes}")

        # Step 2: layer_files에서 import된 DQM.java 파일만 찾기
        dqm_java_files = []
        for layer_key in ["dqm", "repository"]:
            layer_files_list = table_access_info.layer_files.get(layer_key, [])
            for file_path in layer_files_list:
                if not file_path.lower().endswith(".java"):
                    continue
                file_name = Path(file_path).stem  # 예: UserDQM
                if file_name in imported_dqm_classes:
                    if file_path not in dqm_java_files:
                        dqm_java_files.append(file_path)

        if not dqm_java_files:
            logger.debug("layer_files에서 매칭되는 DQM.java 파일을 찾지 못했습니다.")
            return ""

        logger.info(f"Planning에 포함할 DQM.java 파일: {len(dqm_java_files)}개")

        # Step 3: DQM.java 파일 내용 읽어서 포맷팅
        output_parts = []
        for file_path in dqm_java_files:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
                file_name = Path(file_path).name
                output_parts.append(f"### {file_name}")
                output_parts.append("")
                output_parts.append("```java")
                output_parts.append(content)
                output_parts.append("```")
                output_parts.append("")
            except Exception as e:
                logger.warning(f"DQM.java 파일 읽기 실패: {file_path} - {e}")
                continue

        return "\n".join(output_parts)

    # ========== Phase 2 오버라이드: CCS 전용 Planning ==========

    def _create_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> str:
        """
        CCS 전용 Phase 2 (Planning) 프롬프트를 생성합니다.

        부모 클래스의 로직에 ccs_util_info 변수를 추가하고,
        CCS 전용 planning 템플릿을 사용합니다.
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # 소스 파일 내용
        add_line_num: bool = self.config and self.config.generate_type != "full_source"
        source_files_str = self._read_file_contents(
            modification_context.file_paths, add_line_num=add_line_num
        )

        # mapping_info (Phase 1 결과)를 JSON 문자열로 변환
        mapping_info_str = json.dumps(mapping_info, indent=2, ensure_ascii=False)

        # Call Stacks 정보
        call_stacks_str = self._get_callstacks_from_table_access_info(
            modification_context.file_paths, table_access_info
        )

        # DQM.java 정보 추출 (XML query id ↔ Java 메서드 매핑용)
        dqm_java_info = self._extract_dqm_java_info(
            modification_context, table_access_info
        )

        # CCS 유틸리티 클래스명 결정 (Jinja2 치환용)
        common_util = (
            self.ccs_util_info.get("common_util", "SliEncryptionUtil")
            if self.ccs_util_info
            else "SliEncryptionUtil"
        )
        masking_util = (
            self.ccs_util_info.get("masking_util", "")
            if self.ccs_util_info
            else ""
        )

        # 템플릿 변수 준비 (CCS 유틸리티 정보 포함)
        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "mapping_info": mapping_info_str,
            "call_stacks": call_stacks_str,
            "dqm_java_info": dqm_java_info,  # DQM.java 파일 내용 (XML↔Java 매핑용)
            "ccs_util_info": self._format_ccs_util_info_for_prompt(),
            "common_util": common_util,      # Jinja2 치환용: BCCommUtil 등
            "masking_util": masking_util,    # Jinja2 치환용: BCMaskingUtil 등
        }

        # CCS 전용 planning 템플릿 사용
        template_str = self._load_template(self.planning_template_ccs_path)
        return self._render_template(template_str, variables)

    # ========== Phase 3 오버라이드: CCS 전용 Execution ==========

    def _create_execution_prompt(
        self,
        modification_context: ModificationContext,
        modification_instructions: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[int, str], Dict[str, str], Dict[str, str]]:
        """
        CCS 전용 Execution 프롬프트를 생성합니다.

        부모 클래스의 로직에 ccs_util_info 변수를 추가하고,
        CCS 전용 execution 템플릿을 사용합니다.

        Returns:
            Tuple[str, Dict[int, str], Dict[str, str], Dict[str, str]]:
                - Execution 프롬프트
                - 인덱스 -> 파일 경로 매핑
                - 파일명 -> 파일 경로 매핑
                - 파일 경로 -> 파일 내용 매핑
        """
        add_line_num = self.config and self.config.generate_type != "full_source"

        # 소스 파일 내용 (인덱스 형식)
        source_files_str, index_to_path, path_to_content = (
            self._read_file_contents_indexed(
                modification_context.file_paths, add_line_num=add_line_num
            )
        )

        # 파일명 -> 파일 경로 매핑 생성
        file_mapping = {Path(fp).name: fp for fp in modification_context.file_paths}

        # 수정 지침을 JSON 문자열로 변환
        instructions_str = json.dumps(
            modification_instructions, indent=2, ensure_ascii=False
        )

        # CCS 유틸리티 클래스명 및 import 경로 결정 (Jinja2 치환용)
        common_util = (
            self.ccs_util_info.get("common_util", "SliEncryptionUtil")
            if self.ccs_util_info
            else "SliEncryptionUtil"
        )
        masking_util = (
            self.ccs_util_info.get("masking_util", "")
            if self.ccs_util_info
            else ""
        )
        package_prefix = (
            self.ccs_util_info.get("package_prefix", "")
            if self.ccs_util_info
            else ""
        )

        # 전체 import 경로 생성: sli.ccs.{prefix}.svcutil.{UtilClass}
        common_util_import = (
            f"sli.ccs.{package_prefix}.svcutil.{common_util}"
            if package_prefix
            else ""
        )
        masking_util_import = (
            f"sli.ccs.{package_prefix}.svcutil.{masking_util}"
            if package_prefix and masking_util
            else ""
        )

        # 템플릿 변수 준비 (CCS 유틸리티 정보 포함)
        variables = {
            "source_files": source_files_str,
            "modification_instructions": instructions_str,
            "ccs_util_info": self._format_ccs_util_info_for_prompt(),
            "common_util": common_util,                  # 클래스명: BCCommonUtil 등
            "masking_util": masking_util,                # 클래스명: BCMaskingUtil 등
            "common_util_import": common_util_import,    # 전체 import 경로
            "masking_util_import": masking_util_import,  # 전체 import 경로
        }

        # CCS 전용 execution 템플릿 사용
        template_str = self._load_template(self.execution_template_ccs_path)
        prompt = self._render_template(template_str, variables)

        return prompt, index_to_path, file_mapping, path_to_content
