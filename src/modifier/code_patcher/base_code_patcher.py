import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from config.config_manager import Configuration

logger = logging.getLogger("applycrypto.code_patcher")


class BaseCodePatcher(ABC):
    """
    Abstract base class for code patchers.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        config: Optional[Configuration] = None,
    ):
        """
        Initialize BaseCodePatcher.

        Args:
            project_root: Root directory of the project (optional).
            config: Configuration object (optional).
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config = config

    def _normalize_file_path(
        self, file_path: Path
    ) -> Tuple[Path, Optional[str]]:
        """파일 경로를 정규화하고 존재 여부를 검증합니다.

        Returns:
            Tuple[Path, Optional[str]]:
                (정규화된 경로, 에러 메시지 또는 None)
        """
        if not file_path.is_absolute():
            logger.warning(
                f"Relative path passed: {file_path}. Converting to absolute."
            )
            file_path = self.project_root / file_path
        file_path = file_path.resolve()
        if not file_path.exists():
            error_msg = f"File does not exist: {file_path}"
            logger.error(error_msg)
            return file_path, error_msg
        return file_path, None

    @abstractmethod
    def apply_patch(
        self, file_path: Path, modified_code: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply changes to a file.

        Args:
            file_path: Path to the file to modify.
            modified_code: The code or diff to apply.
            dry_run: If True, simulate the operation without changes.

        Returns:
            Tuple[bool, Optional[str]]: (Success, Error message)
        """
        pass

    def validate_syntax(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate the syntax of the modified file.

        Args:
            file_path: Path to the file to validate.

        Returns:
            Tuple[bool, Optional[str]]: (Valid, Error message)
        """
        try:
            file_path, error_msg = self._normalize_file_path(file_path)
            if error_msg:
                return False, error_msg

            # Java syntax check
            if file_path.suffix == ".java":
                result = subprocess.run(
                    ["javac", "-Xlint:all", "-cp", ".", str(file_path)],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

                if result.returncode != 0:
                    error_msg = f"Java syntax error: {result.stderr}"
                    logger.warning(error_msg)
                    return False, error_msg

            # XML syntax check
            elif file_path.suffix == ".xml":
                result = subprocess.run(
                    ["xmllint", "--noout", str(file_path)],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

                if result.returncode != 0:
                    error_msg = f"XML syntax error: {result.stderr}"
                    logger.warning(error_msg)
                    return False, error_msg

            return True, None

        except FileNotFoundError:
            logger.debug("Syntax check tools not found, skipping.")
            return True, None
        except Exception as e:
            logger.warning(f"Error during syntax check: {e}")
            return True, None
