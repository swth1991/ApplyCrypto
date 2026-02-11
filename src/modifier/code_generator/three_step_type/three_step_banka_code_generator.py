"""
Three-Step Banka (BNK Online) Code Generator

BNK 온라인 타입 전용 3단계 LLM 협업 코드 생성기입니다.

기존 ThreeStepCodeGenerator를 상속하며, Phase 2(Planning)에서
BIZ 파일의 전체 내용 대신 call_stack에서 참조되는 메서드만 추출하여
프롬프트 길이를 최적화합니다.

Phase 1(Data Mapping)과 Phase 3(Execution)은 부모 클래스와 동일하게 동작합니다.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from config.config_manager import Configuration
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from parser.java_ast_parser import JavaASTParser

from .three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")


class ThreeStepBankaCodeGenerator(ThreeStepCodeGenerator):
    """BNK 온라인 전용 ThreeStep 코드 생성기

    SVC가 여러 BIZ를 호출하고 각 BIZ 파일이 수천 줄 이상일 수 있어
    Phase 2 프롬프트가 LLM max token을 초과하는 문제를 해결합니다.

    해결 방식:
    - BIZ 파일: call_stack에서 참조되는 메서드만 추출 (JavaASTParser의 line_number/end_line_number 활용)
    - 비-BIZ 파일 (SVC, DEM, DQM 등): 전체 내용 포함
    """

    def __init__(self, config: Configuration):
        super().__init__(config)
        self._java_parser = JavaASTParser()

    # ========== Phase 2 오버라이드 ==========

    def _create_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> str:
        """Phase 2 (Planning) 프롬프트를 생성합니다.

        BIZ 파일은 call_stack 기반 메서드만, 나머지 파일은 전체 내용을 포함합니다.
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # call_stacks 원본 데이터 추출 (메서드 필터링에 사용)
        raw_call_stacks = self._extract_raw_call_stacks(
            modification_context.file_paths, table_access_info
        )
        call_stacks_str = json.dumps(raw_call_stacks, indent=2, ensure_ascii=False)

        # source_files: BIZ=메서드만, 나머지=전체
        add_line_num: bool = (
            self.config and self.config.generate_type != "full_source"
        )
        source_files_str = self._build_optimized_source_files(
            modification_context.file_paths,
            raw_call_stacks,
            add_line_num=add_line_num,
        )

        # mapping_info (Phase 1 결과)
        mapping_info_str = json.dumps(mapping_info, indent=2, ensure_ascii=False)

        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "mapping_info": mapping_info_str,
            "call_stacks": call_stacks_str,
        }

        template_str = self._load_template(self.planning_template_path)
        return self._render_template(template_str, variables)

    # ========== 헬퍼 메서드 ==========

    def _is_biz_file(self, file_path: str) -> bool:
        """BIZ 파일 여부 판별 — stem이 'BIZ'로 끝나는 파일만

        Util 파일(BIZUtil, StringUtil 등)은 제외합니다.
        """
        return Path(file_path).stem.endswith("BIZ")

    def _extract_raw_call_stacks(
        self,
        file_paths: List[str],
        table_access_info: TableAccessInfo,
    ) -> List[List[str]]:
        """call_stacks를 List[List[str]]로 반환합니다 (JSON 직렬화 전).

        base_code_generator._get_callstacks_from_table_access_info()와
        동일한 필터링 로직이지만, JSON 문자열 대신 원본 리스트를 반환합니다.
        """
        call_stacks_list: List[List[str]] = []

        file_class_names = [Path(fp).stem for fp in file_paths]

        for sql_query in table_access_info.sql_queries:
            call_stacks = sql_query.get("call_stacks", [])
            if not call_stacks:
                continue

            for call_stack in call_stacks:
                if not isinstance(call_stack, list) or not call_stack:
                    continue

                first_method = call_stack[0]
                if not isinstance(first_method, str):
                    continue

                if "." in first_method:
                    method_class_name = first_method.split(".")[0]
                else:
                    method_class_name = first_method

                if method_class_name in file_class_names:
                    if call_stack not in call_stacks_list:
                        call_stacks_list.append(call_stack)

        return call_stacks_list

    def _get_target_methods_for_file(
        self,
        file_path: str,
        raw_call_stacks: List[List[str]],
    ) -> Set[str]:
        """call_stacks에서 특정 파일 클래스에 해당하는 메서드명을 수집합니다."""
        class_name = Path(file_path).stem
        target_methods: Set[str] = set()

        for call_stack in raw_call_stacks:
            for method_sig in call_stack:
                if "." in method_sig:
                    cls, method = method_sig.split(".", 1)
                    if cls == class_name:
                        target_methods.add(method)

        return target_methods

    def _extract_methods_from_biz_file(
        self,
        file_path: str,
        raw_call_stacks: List[List[str]],
        add_line_num: bool = False,
    ) -> str:
        """BIZ 파일에서 call_stack에 참조되는 메서드만 추출합니다.

        알고리즘:
        1. call_stacks에서 이 파일 클래스의 메서드명 수집
        2. JavaASTParser로 파일 파싱 → 메서드별 line_number/end_line_number 획득
        3. 매칭 메서드의 라인 범위만 추출

        Fallback: call_stack에 매칭되는 메서드가 없으면 전체 파일 반환
        """
        target_methods = self._get_target_methods_for_file(
            file_path, raw_call_stacks
        )

        if not target_methods:
            logger.debug(
                f"BIZ 파일에 call_stack 메서드 없음, 전체 포함: {Path(file_path).name}"
            )
            return self._read_single_file(file_path, add_line_num)

        # JavaASTParser로 메서드 정보 획득
        tree, error = self._java_parser.parse_file(Path(file_path))
        if error:
            logger.warning(
                f"BIZ 파일 파싱 실패, 전체 포함: {Path(file_path).name} - {error}"
            )
            return self._read_single_file(file_path, add_line_num)

        classes = self._java_parser.extract_class_info(tree, Path(file_path))

        # 매칭 메서드의 라인 범위 수집
        method_ranges: List[tuple] = []
        for cls_info in classes:
            for method in cls_info.methods:
                if method.name in target_methods:
                    method_ranges.append(
                        (method.name, method.line_number, method.end_line_number)
                    )

        if not method_ranges:
            logger.debug(
                f"BIZ 파일에서 매칭 메서드 없음, 전체 포함: {Path(file_path).name}"
            )
            return self._read_single_file(file_path, add_line_num)

        # 파일에서 해당 라인만 추출
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
        except Exception as e:
            logger.warning(f"BIZ 파일 읽기 실패: {file_path} - {e}")
            return ""

        extracted_parts: List[str] = []
        for method_name, start_line, end_line in sorted(
            method_ranges, key=lambda x: x[1]
        ):
            # line_number는 1-based, 리스트 인덱스는 0-based
            lines = all_lines[start_line - 1 : end_line]
            if add_line_num:
                numbered = [
                    f"{start_line + i}|{line.rstrip()}"
                    for i, line in enumerate(lines)
                ]
                extracted_parts.append(
                    f"// --- Method: {method_name} (lines {start_line}-{end_line}) ---\n"
                    + "\n".join(numbered)
                )
            else:
                extracted_parts.append(
                    f"// --- Method: {method_name} (lines {start_line}-{end_line}) ---\n"
                    + "".join(lines)
                )

        matched_names = [r[0] for r in method_ranges]
        logger.info(
            f"BIZ 메서드 추출: {Path(file_path).name} → "
            f"{len(method_ranges)}개 메서드 ({', '.join(matched_names)})"
        )

        return "\n\n".join(extracted_parts)

    def _read_single_file(
        self, file_path: str, add_line_num: bool = False
    ) -> str:
        """단일 파일의 전체 내용을 읽습니다."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if add_line_num:
                return "\n".join(
                    f"{idx}|{line.rstrip()}" for idx, line in enumerate(lines, 1)
                )
            return "".join(lines)
        except Exception as e:
            logger.warning(f"파일 읽기 실패: {file_path} - {e}")
            return ""

    def _build_optimized_source_files(
        self,
        file_paths: List[str],
        raw_call_stacks: List[List[str]],
        add_line_num: bool = False,
    ) -> str:
        """BIZ 파일은 메서드만, 나머지는 전체 내용으로 source_files 문자열을 생성합니다."""
        snippets: List[str] = []

        for file_path in file_paths:
            file_name = Path(file_path).name

            if self._is_biz_file(file_path):
                # BIZ 파일: call_stack 기반 메서드만 추출
                content = self._extract_methods_from_biz_file(
                    file_path, raw_call_stacks, add_line_num
                )
                snippets.append(
                    f"=== File: {file_name} (call_stack methods only) ===\n{content}"
                )
            else:
                # 비-BIZ 파일: 전체 내용
                content = self._read_single_file(file_path, add_line_num)
                snippets.append(f"=== File: {file_name} ===\n{content}")

        return "\n\n".join(snippets)
