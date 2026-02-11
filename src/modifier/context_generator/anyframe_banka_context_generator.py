"""
Anyframe Banka Context Generator

BNK 온라인 타입 전용 Context Generator입니다.
AnyframeContextGenerator의 SVC→BIZ→DEM/DQM 그룹핑 로직을 그대로 재사용하고,
create_batches()만 오버라이드하여 BIZ 파일의 토큰을 메서드 레벨로 계산합니다.

문제:
  BaseContextGenerator.create_batches()는 파일 전체 내용으로 토큰을 계산하지만,
  ThreeStepBankaCodeGenerator의 Phase 2 프롬프트에서는 BIZ 파일의 call_stack
  참조 메서드만 사용합니다. 이로 인해 토큰이 과대 추정되어 불필요한 배치 분할 발생.

해결:
  BIZ 파일은 call_stack 기반 메서드 내용만으로 토큰을 계산하여 배치 분할을 최적화합니다.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from config.config_manager import Configuration
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from modifier.code_generator.base_code_generator import BaseCodeGenerator
from modifier.context_generator.anyframe_context_generator import (
    AnyframeContextGenerator,
)
from parser.java_ast_parser import JavaASTParser

logger = logging.getLogger("applycrypto.anyframe_banka_context_generator")


class AnyframeBankaContextGenerator(AnyframeContextGenerator):
    """BNK 온라인 전용 Context Generator

    AnyframeContextGenerator를 상속하여 SVC→BIZ→DEM/DQM 그룹핑 로직은
    그대로 재사용하고, create_batches()만 오버라이드합니다.

    BIZ 파일의 토큰을 call_stack 참조 메서드만으로 계산하여
    실제 Phase 2 프롬프트 크기에 가까운 추정치를 사용합니다.
    """

    def __init__(self, config: Configuration, code_generator: BaseCodeGenerator):
        super().__init__(config, code_generator)
        self._java_parser = JavaASTParser()
        self._table_access_info: Optional[TableAccessInfo] = None

    # ========== generate 오버라이드 ==========

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
        table_access_info: Optional[TableAccessInfo] = None,
        endpoint_method: Optional[str] = None,
    ) -> List[ModificationContext]:
        """table_access_info를 인스턴스 변수로 저장 후 부모 generate() 호출

        부모의 generate()가 내부적으로 self.create_batches()를 호출하므로,
        오버라이드된 create_batches()에서 table_access_info를 사용할 수 있습니다.
        """
        self._table_access_info = table_access_info
        return super().generate(
            layer_files, table_name, columns, table_access_info, endpoint_method
        )

    # ========== create_batches 오버라이드 ==========

    def create_batches(
        self,
        file_paths: List[str],
        table_name: str,
        columns: List[Dict],
        layer: str = "",
        context_files: List[str] = None,
    ) -> List[ModificationContext]:
        """BIZ 파일은 메서드 레벨 토큰으로 계산하여 배치 분할

        BaseContextGenerator.create_batches()와 동일한 배치 분할 로직이지만,
        BIZ 파일의 토큰을 전체 파일 대신 call_stack 참조 메서드만으로 계산합니다.

        table_access_info가 없으면 부모 로직(전체 파일 기반)으로 fallback.
        """
        if not self._table_access_info:
            return super().create_batches(
                file_paths, table_name, columns, layer, context_files
            )

        if context_files is None:
            context_files = []
        if not file_paths:
            return []

        # call_stacks 추출
        raw_call_stacks = self._extract_raw_call_stacks(
            file_paths, self._table_access_info
        )

        batches: List[ModificationContext] = []
        current_paths: List[str] = []

        # 기본 정보 준비 (부모와 동일)
        from models.code_generator import CodeGeneratorInput

        table_info = {
            "table_name": table_name,
            "columns": columns,
        }
        formatted_table_info = json.dumps(table_info, indent=2, ensure_ascii=False)
        max_tokens = self._config.max_tokens_per_batch

        input_empty_data = CodeGeneratorInput(
            file_paths=[], table_info=formatted_table_info, layer_name=layer
        )

        empty_prompt = self._code_generator.create_prompt(input_empty_data)
        empty_num_tokens = self._code_generator.calculate_token_size(empty_prompt)
        separator_tokens = self._code_generator.calculate_token_size("\n\n")

        current_batch_tokens = empty_num_tokens

        for file_path in file_paths:
            try:
                path_obj = Path(file_path)
                if not path_obj.exists():
                    logger.warning(
                        f"File not found during batch creation: {file_path}"
                    )
                    continue

                # ━━━ 핵심 차이: BIZ 파일은 메서드만으로 토큰 계산 ━━━
                if self._is_biz_file(file_path):
                    content = self._get_biz_method_content(
                        file_path, raw_call_stacks
                    )
                else:
                    with open(path_obj, "r", encoding="utf-8") as f:
                        content = f.read()

            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                continue

            snippet_formatted = (
                f"=== File Path (Absolute): {file_path} ===\n{content}"
            )
            snippet_tokens = self._code_generator.calculate_token_size(
                snippet_formatted
            )

            tokens_to_add = snippet_tokens
            if current_paths:
                tokens_to_add += separator_tokens

            if current_paths and (current_batch_tokens + tokens_to_add) > max_tokens:
                batches.append(
                    ModificationContext(
                        file_paths=current_paths,
                        table_name=table_name,
                        columns=columns,
                        file_count=len(current_paths),
                        layer=layer,
                        context_files=context_files,
                    )
                )
                current_paths = [file_path]
                current_batch_tokens = empty_num_tokens + snippet_tokens
            else:
                current_paths.append(file_path)
                current_batch_tokens += tokens_to_add

        if current_paths:
            batches.append(
                ModificationContext(
                    file_paths=current_paths,
                    table_name=table_name,
                    columns=columns,
                    file_count=len(current_paths),
                    layer=layer,
                    context_files=context_files,
                )
            )

        logger.info(
            f"Split {len(file_paths)} files into {len(batches)} batches "
            f"(BIZ method-level token estimation)."
        )
        return batches

    # ========== BIZ 메서드 추출 헬퍼 ==========

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
        """call_stacks를 List[List[str]]로 반환합니다.

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

    def _get_biz_method_content(
        self,
        file_path: str,
        raw_call_stacks: List[List[str]],
    ) -> str:
        """BIZ 파일에서 call_stack 참조 메서드만 추출하여 텍스트 반환합니다.

        토큰 계산용으로 순수 메서드 코드만 반환합니다.
        매칭 메서드 없으면 전체 파일 내용을 반환합니다 (fallback).
        """
        target_methods = self._get_target_methods_for_file(
            file_path, raw_call_stacks
        )

        if not target_methods:
            logger.debug(
                f"BIZ 파일에 call_stack 메서드 없음, 전체 포함: {Path(file_path).name}"
            )
            return self._read_full_file(file_path)

        # JavaASTParser로 메서드 정보 획득
        tree, error = self._java_parser.parse_file(Path(file_path))
        if error:
            logger.warning(
                f"BIZ 파일 파싱 실패, 전체 포함: {Path(file_path).name} - {error}"
            )
            return self._read_full_file(file_path)

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
            return self._read_full_file(file_path)

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
            lines = all_lines[start_line - 1 : end_line]
            extracted_parts.append("".join(lines))

        matched_names = [r[0] for r in method_ranges]
        logger.info(
            f"BIZ 토큰 추정 (메서드 레벨): {Path(file_path).name} -> "
            f"{len(method_ranges)}개 메서드 ({', '.join(matched_names)})"
        )

        return "\n\n".join(extracted_parts)

    def _read_full_file(self, file_path: str) -> str:
        """단일 파일의 전체 내용을 읽습니다."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"파일 읽기 실패: {file_path} - {e}")
            return ""
