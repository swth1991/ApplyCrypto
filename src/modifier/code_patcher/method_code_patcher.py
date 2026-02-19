import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_code_patcher import BaseCodePatcher

logger = logging.getLogger("applycrypto.code_patcher")


class MethodCodePatcher(BaseCodePatcher):
    """메서드 단위 수정을 원본 파일에 적용하는 코드 패처.

    modified_code로 JSON 문자열을 받아 파싱하고:
    1. 원본 파일을 읽음
    2. 각 메서드를 end_line 역순으로 교체 (bottom-up)
    3. 누락된 import를 추가
    4. 수정된 파일을 저장

    JSON 포맷:
    {
        "methods": [
            {
                "method_name": "processCustomer",
                "start_line": 42,
                "end_line": 78,
                "modified_code": "    public void processCustomer() {...}"
            }
        ],
        "imports": [
            "import sli.fw.online.SliEncryptionUtil;",
            "import sli.fw.online.constants.SliEncryptionConstants;"
        ]
    }
    """

    def apply_patch(
        self, file_path: Path, modified_code: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """JSON 메서드 수정 데이터를 파싱하여 원본 파일에 적용합니다.

        Args:
            file_path: 수정할 파일 경로
            modified_code: JSON 문자열 (메서드 수정 + import 정보)
            dry_run: True이면 시뮬레이션만 수행

        Returns:
            Tuple[bool, Optional[str]]: (성공 여부, 에러 메시지)
        """
        try:
            if not file_path.is_absolute():
                logger.warning(
                    f"Relative path passed: {file_path}. Converting to absolute."
                )
                file_path = self.project_root / file_path

            file_path = file_path.resolve()

            if not file_path.exists():
                error_msg = f"File does not exist: {file_path}"
                logger.error(error_msg)
                return False, error_msg

            # 1. JSON 파싱
            try:
                patch_data: Dict[str, Any] = json.loads(modified_code)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in modified_code: {e}"
                logger.error(error_msg)
                return False, error_msg

            methods: List[Dict[str, Any]] = patch_data.get("methods", [])
            required_imports: List[str] = patch_data.get("imports", [])

            if not methods:
                error_msg = "No method modifications in JSON data"
                logger.warning(error_msg)
                return False, error_msg

            if dry_run:
                logger.info(
                    f"[DRY RUN] Method patch simulation: {file_path} "
                    f"({len(methods)} methods)"
                )
                return True, None

            # 2. 원본 파일 읽기
            with open(file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # 3. FULL_FILE fallback 처리
            if (
                len(methods) == 1
                and methods[0].get("method_name") == "FULL_FILE"
            ):
                reconstructed = methods[0]["modified_code"]
            else:
                # 4. end_line 기준 역순 정렬 (bottom-up 교체)
                sorted_methods = sorted(
                    methods, key=lambda m: m["end_line"], reverse=True
                )

                for method in sorted_methods:
                    start_line = method["start_line"]
                    end_line = method["end_line"]
                    method_name = method.get("method_name", "unknown")

                    # 범위 검증
                    if not (1 <= start_line <= end_line <= len(all_lines)):
                        error_msg = (
                            f"Invalid method range: {method_name} "
                            f"({start_line}-{end_line}) "
                            f"in file with {len(all_lines)} lines"
                        )
                        logger.error(error_msg)
                        return False, error_msg

                    new_code = method["modified_code"]

                    new_lines = new_code.splitlines(keepends=True)
                    # 마지막 줄에 newline이 없으면 추가
                    if new_lines and not new_lines[-1].endswith("\n"):
                        new_lines[-1] += "\n"

                    all_lines[start_line - 1 : end_line] = new_lines

                    logger.debug(
                        f"메서드 교체: {file_path.name}::{method_name} "
                        f"(lines {start_line}-{end_line})"
                    )

                reconstructed = "".join(all_lines)

            # 5. import 추가
            if required_imports:
                reconstructed = self._ensure_imports(
                    reconstructed, required_imports
                )

            # 6. 파일 쓰기
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(reconstructed)

            logger.info(
                f"Method patch complete: {file_path} "
                f"({len(methods)} methods replaced)"
            )
            return True, None

        except Exception as e:
            error_msg = f"Method patch failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def _ensure_imports(
        source_code: str, required_imports: List[str]
    ) -> str:
        """소스 코드에 필요한 import가 없으면 추가합니다.

        이미 존재하는 import (정확 매칭 또는 와일드카드)는 건너뛰고,
        누락된 것만 마지막 import 문 뒤에 삽입합니다.
        import 문이 전혀 없으면 package 선언 뒤에 삽입합니다.

        Args:
            source_code: 재구성된 전체 소스 코드
            required_imports: 필요한 import 문 리스트

        Returns:
            str: import가 추가된 소스 코드
        """
        lines = source_code.split("\n")

        missing_imports: List[str] = []
        for imp in required_imports:
            # import 문의 핵심 클래스명 추출 (예: "SliEncryptionUtil")
            class_name = imp.split(".")[-1].rstrip(";")
            # 패키지명 추출 (예: "sli.fw.online")
            package_name = imp.replace("import ", "").rsplit(".", 1)[0]

            has_exact = any(
                line.strip().startswith("import ") and class_name in line
                for line in lines
            )
            has_wildcard = any(
                line.strip().startswith("import ")
                and f"{package_name}.*" in line
                for line in lines
            )
            if not (has_exact or has_wildcard):
                missing_imports.append(imp)

        if not missing_imports:
            return source_code

        # 마지막 import 문 위치 찾기
        last_import_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import "):
                last_import_idx = i

        if last_import_idx >= 0:
            # 마지막 import 바로 뒤에 삽입
            for j, imp in enumerate(missing_imports):
                lines.insert(last_import_idx + 1 + j, imp)
        else:
            # import가 없으면 package 선언 뒤에 삽입
            package_idx = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("package "):
                    package_idx = i
                    break

            insert_idx = package_idx + 1 if package_idx >= 0 else 0
            lines.insert(insert_idx, "")
            for j, imp in enumerate(missing_imports):
                lines.insert(insert_idx + 1 + j, imp)

        logger.info(f"import 추가: {missing_imports}")
        return "\n".join(lines)
