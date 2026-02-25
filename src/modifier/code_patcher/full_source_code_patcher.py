import logging
from pathlib import Path
from typing import Optional, Tuple

from .base_code_patcher import BaseCodePatcher

logger = logging.getLogger(__name__)


class FullSourceCodePatcher(BaseCodePatcher):
    """
    Code patcher that replaces the full source code of a file.
    """

    def apply_patch(
        self, file_path: Path, modified_code: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Overwrite the file with full source code.
        """
        try:
            file_path, error_msg = self._normalize_file_path(file_path)
            if error_msg:
                return False, error_msg

            if dry_run:
                logger.info(f"[DRY RUN] Overwrite Simulation: {file_path}")
                return True, None

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(modified_code)

            logger.info(f"Full source overwrite complete: {file_path}")
            return True, None

        except Exception as e:
            error_msg = f"Full source overwrite failed: {e}"
            logger.error(error_msg)
            return False, error_msg
