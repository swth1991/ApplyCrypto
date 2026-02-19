"""
Three-Step Banka (BNK Online) Code Generator

BNK 온라인 타입 전용 3단계 LLM 협업 코드 생성기입니다.

기존 ThreeStepCodeGenerator를 상속하며:
- Phase 2(Planning): BIZ 파일의 전체 내용 대신 call_stack에서 참조되는 메서드만 추출
- Phase 3(Execution): generate_type="method"일 때 modification_instructions의
  대상 메서드만 추출하여 전달하고, 수정 결과를 JSON으로 패킹 (파일 재구성은 MethodCodePatcher가 수행)

Phase 1(Data Mapping)은 부모 클래스와 동일하게 동작합니다 (VO 파일 제외).
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from config.config_manager import Configuration
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from parser.java_ast_parser import JavaASTParser

from .three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")


@dataclass
class MethodIndexEntry:
    """Phase 3 method 모드에서 메서드 인덱스 메타데이터

    LLM 프롬프트의 [METHOD_N] 인덱스와 원본 파일의 메서드 위치를
    매핑하는 데 사용됩니다. 응답 파싱 후 원본 파일 재구성 시
    정확한 라인 범위 교체를 위해 필요합니다.
    """

    index: int  # METHOD_N 인덱스 (1-based)
    file_path: str  # 원본 파일의 절대 경로
    method_name: str  # 메서드 이름
    start_line: int  # 원본 파일에서의 시작 라인 (1-based, AST 기준)
    end_line: int  # 원본 파일에서의 끝 라인 (1-based, AST 기준)


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

        # method 모드용 execution 템플릿 로드
        if self.config.generate_type == "method":
            template_dir = Path(__file__).parent
            self._method_execution_template_path = (
                template_dir / "execution_template_banka_method.md"
            )
            if not self._method_execution_template_path.exists():
                raise FileNotFoundError(
                    f"Method 모드 execution 템플릿을 찾을 수 없습니다: "
                    f"{self._method_execution_template_path}"
                )

        # Phase 3 method 모드에서 메서드 인덱스 매핑 (프롬프트 생성 → 응답 파싱 간 공유)
        self._method_index_map: Dict[int, MethodIndexEntry] = {}

    def _get_execution_template_path(self) -> Path:
        """method 모드일 때 전용 method-level 템플릿 반환"""
        if self.config.generate_type == "method":
            return self._method_execution_template_path
        return super()._get_execution_template_path()

    # ========== Phase 1 오버라이드 (VO 제외) ==========

    def _create_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """Phase 1 (Data Mapping) 프롬프트 — banka는 VO 파일 제외

        banka 타입에서는 VO 파일을 Phase 1 프롬프트에 포함시키지 않습니다.
        SQL 쿼리와 테이블 정보만으로 데이터 매핑을 분석합니다.
        """
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        sql_queries_str = self._get_sql_queries_for_prompt(
            table_access_info, modification_context.file_paths
        )

        variables = {
            "table_info": table_info_str,
            "vo_files": "",  # banka에서는 Phase 1에 VO 포함하지 않음
            "sql_queries": sql_queries_str,
        }

        template_str = self._load_template(self.data_mapping_template_path)
        return self._render_template(template_str, variables)

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
        """BIZ 파일 여부 판별 — stem이 'BIZ'로 끝나는 파일만 (대소문자 무시)

        Util 파일(BIZUtil, StringUtil 등)은 제외합니다.
        """
        return Path(file_path).stem.upper().endswith("BIZ")

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

    # 메서드 추출 시 앞뒤 패딩 라인 수
    # tree-sitter AST가 메서드 범위를 부정확하게 잡는 경우를 대비하여 여유있게 설정
    BIZ_METHOD_PADDING_BEFORE = 20
    BIZ_METHOD_PADDING_AFTER = 20

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
        3. 매칭 메서드의 라인 범위 + 앞뒤 패딩을 추출

        앞쪽 패딩(BIZ_METHOD_PADDING_BEFORE)은 어노테이션(@Override, @Transactional 등)과
        Javadoc 주석을 포함하기 위해 필요하고, 뒤쪽 패딩(BIZ_METHOD_PADDING_AFTER)은
        메서드 종료 후 컨텍스트를 포함합니다.

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
        tree, error = self._java_parser.parse_file(Path(file_path), remove_comments=False)
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

        total_lines = len(all_lines)
        extracted_parts: List[str] = []
        for method_name, start_line, end_line in sorted(
            method_ranges, key=lambda x: x[1]
        ):
            # 앞뒤 패딩 적용 (파일 범위 클램핑)
            padded_start = max(1, start_line - self.BIZ_METHOD_PADDING_BEFORE)
            padded_end = min(total_lines, end_line + self.BIZ_METHOD_PADDING_AFTER)

            # line_number는 1-based, 리스트 인덱스는 0-based
            lines = all_lines[padded_start - 1 : padded_end]
            if add_line_num:
                numbered = [
                    f"{padded_start + i}|{line.rstrip()}"
                    for i, line in enumerate(lines)
                ]
                extracted_parts.append(
                    f"// --- Method: {method_name} (lines {padded_start}-{padded_end}) ---\n"
                    + "\n".join(numbered)
                )
            else:
                extracted_parts.append(
                    f"// --- Method: {method_name} (lines {padded_start}-{padded_end}) ---\n"
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

    # ========== Phase 3 오버라이드 (method 모드) ==========

    # BNK banka에서 encryption 적용 시 필요한 import 문
    _ENCRYPTION_IMPORTS = [
        "import sli.fw.online.SliEncryptionUtil;",
        "import sli.fw.online.constants.SliEncryptionConstants;",
    ]

    def _execute_execution_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        modification_instructions: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Phase 3 (Execution)을 실행합니다.

        generate_type="method"일 때 메서드 단위 추출/수정/재조립을 수행합니다.
        그 외 generate_type에서는 부모 클래스의 기본 동작(전체 파일)을 따릅니다.

        Method 모드 흐름:
        1. modification_instructions에서 파일별 대상 메서드 수집
        2. AST로 대상 메서드 추출 → [METHOD_N] 프롬프트 생성
        3. LLM 호출
        4. ======METHOD_N====== 블록 파싱
        5. 메서드 수정 정보를 파일별 JSON으로 패킹 (파일 재구성은 MethodCodePatcher가 수행)
        """
        if self.config.generate_type != "method":
            return super()._execute_execution_phase(
                session_dir, modification_context, modification_instructions
            )

        # === Method-level execution ===
        step_config = self._get_step_config()
        logger.info("-" * 40)
        logger.info("[Execution Phase - Method Mode] 시작...")
        logger.info(f"Provider: {step_config.execution_provider}")
        logger.info(f"Model: {step_config.execution_model}")

        # 1. modification_instructions에서 파일별 대상 메서드 수집
        file_method_map = self._build_file_method_map(
            modification_context.file_paths, modification_instructions
        )
        logger.info(
            f"대상 파일 수: {len(file_method_map)}, "
            f"총 메서드 수: {sum(len(m) for m in file_method_map.values())}"
        )

        if not file_method_map:
            logger.warning("수정 대상 메서드가 없습니다. 빈 결과를 반환합니다.")
            return [], 0

        # 2. 메서드 단위 프롬프트 생성
        prompt, method_index_info = self._create_method_execution_prompt(
            modification_context, modification_instructions, file_method_map
        )
        self._method_index_map = {
            entry.index: entry for entry in method_index_info
        }
        logger.debug(f"Method Execution 프롬프트 길이: {len(prompt)} chars")
        logger.info(f"추출된 메서드 수: {len(method_index_info)}")

        # 프롬프트 저장
        self._save_prompt_to_file(prompt, modification_context, "execution_method")

        # 3. LLM 호출
        response = self._get_execution_provider().call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Method Execution LLM 응답 완료 (토큰: {tokens_used})")

        # 4. 메서드 단위 응답 파싱
        modified_methods = self._parse_method_execution_response(response)

        # 5. 메서드 수정 정보를 파일별 JSON으로 패킹 (재구성은 MethodCodePatcher가 수행)
        reconstructed_files = self._pack_method_modifications(modified_methods)

        # 6. 결과 저장
        execution_step_number = self._get_execution_step_number()
        execution_result = {
            "mode": "method",
            "modifications": [
                {
                    "file_path": mod.get("file_path"),
                    "code_length": len(mod.get("modified_code", "")),
                }
                for mod in reconstructed_files
            ],
            "method_count": len(method_index_info),
            "modified_method_count": len(modified_methods),
            "raw_response_length": len(response.get("content", "")),
        }
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=execution_step_number,
            phase_name="execution",
            result=execution_result,
            tokens_used=tokens_used,
        )

        return reconstructed_files, tokens_used

    def _build_file_method_map(
        self,
        file_paths: List[str],
        modification_instructions: List[Dict[str, Any]],
    ) -> Dict[str, Set[str]]:
        """modification_instructions에서 파일별 대상 메서드명을 수집합니다.

        SKIP action은 제외하고, 실제 수정이 필요한 메서드만 수집합니다.

        Args:
            file_paths: 현재 배치의 파일 경로 리스트
            modification_instructions: Phase 2에서 생성된 수정 지침

        Returns:
            Dict[str, Set[str]]: 파일 경로 → 대상 메서드명 집합
        """
        name_to_path = {Path(fp).name: fp for fp in file_paths}
        file_method_map: Dict[str, Set[str]] = {}

        for instr in modification_instructions:
            file_name = instr.get("file_name", "")
            target_method = instr.get("target_method", "")
            action = instr.get("action", "").upper()

            if not file_name or not target_method or action == "SKIP":
                continue

            file_path = name_to_path.get(file_name)
            if file_path:
                file_method_map.setdefault(file_path, set()).add(target_method)
            else:
                logger.warning(
                    f"modification_instructions의 파일을 찾을 수 없음: {file_name}"
                )

        return file_method_map

    def _create_method_execution_prompt(
        self,
        modification_context: ModificationContext,
        modification_instructions: List[Dict[str, Any]],
        file_method_map: Dict[str, Set[str]],
    ) -> Tuple[str, List[MethodIndexEntry]]:
        """메서드 단위 Execution 프롬프트를 생성합니다.

        각 파일의 대상 메서드를 JavaASTParser로 추출하여 [METHOD_N] 인덱스와 함께
        프롬프트를 구성합니다.

        Args:
            modification_context: 수정 컨텍스트
            modification_instructions: Phase 2에서 생성된 수정 지침
            file_method_map: 파일 경로 → 대상 메서드명 집합

        Returns:
            Tuple[str, List[MethodIndexEntry]]:
                - 렌더링된 프롬프트 문자열
                - 메서드 인덱스 메타데이터 리스트
        """
        method_snippets: List[str] = []
        method_index_info: List[MethodIndexEntry] = []
        method_idx = 0

        for file_path in modification_context.file_paths:
            target_methods = file_method_map.get(file_path, set())
            if not target_methods:
                continue

            # AST로 메서드 정보 획득
            tree, error = self._java_parser.parse_file(
                Path(file_path), remove_comments=False
            )
            if error:
                # 대형 파일은 FULL_FILE fallback 시 max token 초과 위험
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        total_lines = sum(1 for _ in f)
                except Exception:
                    total_lines = 0

                MAX_FALLBACK_LINES = 500
                if total_lines > MAX_FALLBACK_LINES:
                    logger.error(
                        f"AST 파싱 실패 + 파일이 너무 큼 ({total_lines}줄), "
                        f"프롬프트에서 제외: {Path(file_path).name} - {error}"
                    )
                    continue

                # 작은 파일만 전체 내용으로 fallback
                logger.warning(
                    f"파일 파싱 실패, 전체 파일로 fallback ({total_lines}줄): "
                    f"{Path(file_path).name} - {error}"
                )
                method_idx += 1
                content = self._read_single_file(file_path)
                method_snippets.append(
                    f"[METHOD_{method_idx}] {Path(file_path).name}::FULL_FILE\n"
                    f"=== Content ===\n{content}"
                )
                method_index_info.append(
                    MethodIndexEntry(
                        index=method_idx,
                        file_path=file_path,
                        method_name="FULL_FILE",
                        start_line=1,
                        end_line=total_lines,
                    )
                )
                continue

            classes = self._java_parser.extract_class_info(tree, Path(file_path))

            # 파일 전체 라인 읽기
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
            except Exception as e:
                logger.warning(f"파일 읽기 실패: {file_path} - {e}")
                continue

            file_name = Path(file_path).name
            matched_count = 0

            for cls_info in classes:
                for method in cls_info.methods:
                    if method.name not in target_methods:
                        continue

                    method_idx += 1
                    start_line = method.line_number
                    end_line = method.end_line_number

                    # 메서드 코드 추출 (AST 경계 기준)
                    method_lines = all_lines[start_line - 1 : end_line]
                    method_code = "".join(method_lines)

                    method_index_info.append(
                        MethodIndexEntry(
                            index=method_idx,
                            file_path=file_path,
                            method_name=method.name,
                            start_line=start_line,
                            end_line=end_line,
                        )
                    )

                    method_snippets.append(
                        f"[METHOD_{method_idx}] {file_name}::{method.name} "
                        f"(lines {start_line}-{end_line})\n"
                        f"=== Content ===\n{method_code}"
                    )
                    matched_count += 1

            unmatched = target_methods - {
                entry.method_name
                for entry in method_index_info
                if entry.file_path == file_path
            }
            if unmatched:
                logger.warning(
                    f"AST에서 찾지 못한 메서드: {file_name} → {unmatched}"
                )

            logger.info(
                f"Phase 3 메서드 추출: {file_name} → {matched_count}개 메서드"
            )

        # 프롬프트 렌더링
        source_methods_str = "\n\n".join(method_snippets)
        instructions_str = json.dumps(
            modification_instructions, indent=2, ensure_ascii=False
        )

        template_str = self._load_template(self._get_execution_template_path())
        variables = {
            "source_files": source_methods_str,
            "modification_instructions": instructions_str,
        }
        prompt = self._render_template(template_str, variables)

        return prompt, method_index_info

    def _parse_method_execution_response(
        self,
        response: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """LLM 응답에서 ======METHOD_N====== 블록을 파싱합니다.

        Args:
            response: LLM 응답 딕셔너리

        Returns:
            List[Dict[str, Any]]: [{method_index, modified_code}, ...]

        Raises:
            ValueError: 응답에 content가 없는 경우
            Exception: 유효한 METHOD 블록이 없는 경우
        """
        content = response.get("content", "")
        if not content:
            raise ValueError("Method Execution LLM 응답에 content가 없습니다.")

        modified_methods: List[Dict[str, Any]] = []
        blocks = content.split("======END======")

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # METHOD 마커 찾기
            method_marker = re.search(r"======METHOD_(\d+)======", block)
            if not method_marker:
                continue

            idx = int(method_marker.group(1))

            # MODIFIED_CODE 섹션 추출 (들여쓰기 보존, 빈 줄만 제거)
            code_marker = "======MODIFIED_CODE======"
            marker_idx = block.find(code_marker)
            if marker_idx == -1:
                modified_code = ""
            else:
                raw_code = block[marker_idx + len(code_marker):]
                code_lines = raw_code.split("\n")
                # 앞쪽 빈 줄 제거
                while code_lines and not code_lines[0].strip():
                    code_lines.pop(0)
                # 뒤쪽 빈 줄 제거
                while code_lines and not code_lines[-1].strip():
                    code_lines.pop()
                modified_code = "\n".join(code_lines)

            if idx in self._method_index_map:
                entry = self._method_index_map[idx]
                if modified_code:
                    modified_methods.append(
                        {
                            "method_index": idx,
                            "modified_code": modified_code,
                        }
                    )
                    logger.debug(
                        f"METHOD_{idx} 파싱 완료: "
                        f"{Path(entry.file_path).name}::{entry.method_name}"
                    )
                else:
                    logger.debug(
                        f"METHOD_{idx} SKIP: "
                        f"{Path(entry.file_path).name}::{entry.method_name}"
                    )
            else:
                logger.warning(f"알 수 없는 메서드 인덱스: METHOD_{idx}")

        if not modified_methods:
            logger.warning(
                "수정된 메서드가 없습니다 (모든 메서드가 SKIP되었거나 이미 적용됨)."
            )
            return []

        logger.info(f"{len(modified_methods)}개 메서드 수정 정보를 파싱했습니다.")
        return modified_methods

    def _pack_method_modifications(
        self,
        modified_methods: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """파싱된 메서드 수정 정보를 파일별 JSON으로 패킹합니다.

        MethodCodePatcher가 해석할 수 있는 JSON 포맷으로 변환합니다.
        파일 재구성(bottom-up 교체, import 추가)은 MethodCodePatcher가 수행합니다.

        Args:
            modified_methods: [{method_index, modified_code}, ...]

        Returns:
            List[Dict[str, Any]]: [{file_path, modified_code (JSON string)}, ...]
        """
        file_modifications: Dict[str, List[Dict[str, Any]]] = {}

        for mod in modified_methods:
            idx = mod["method_index"]
            entry = self._method_index_map[idx]

            file_modifications.setdefault(entry.file_path, []).append(
                {
                    "method_name": entry.method_name,
                    "start_line": entry.start_line,
                    "end_line": entry.end_line,
                    "modified_code": mod["modified_code"],
                }
            )

        result: List[Dict[str, Any]] = []
        for file_path, methods in file_modifications.items():
            json_data = json.dumps(
                {
                    "methods": methods,
                    "imports": self._ENCRYPTION_IMPORTS,
                },
                ensure_ascii=False,
            )

            result.append(
                {
                    "file_path": file_path,
                    "modified_code": json_data,
                }
            )

            logger.info(
                f"메서드 수정 패킹 완료: {Path(file_path).name} "
                f"({len(methods)}개 메서드)"
            )

        return result
