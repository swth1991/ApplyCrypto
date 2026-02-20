"""
BNK Batch Context Generator

BNK 배치 프로그램용 Context Generator입니다.
BatchBaseContextGenerator를 상속하며, BATVO 검색 범위가 확장됩니다.

BatchBaseContextGenerator와의 차이점:
    - BATVO 수집: batvo/ 하위 + 같은 디렉토리의 *BATVO.java 모두 검색
"""

import logging
from pathlib import Path
from typing import List

from config.config_manager import Configuration

from .batch_base_context_generator import BatchBaseContextGenerator

logger = logging.getLogger(__name__)


class BNKBatchContextGenerator(BatchBaseContextGenerator):
    """
    BNK 배치 프로그램용 Context Generator

    BatchBaseContextGenerator를 상속하며,
    BATVO 파일을 같은 디렉토리에서도 추가로 수집합니다.
    """

    def __init__(self, config: Configuration, code_generator):
        super().__init__(config, code_generator)

    def _find_batvo_files_in_same_dir(self, bat_file_path: str) -> List[str]:
        """
        BAT 파일과 같은 디렉토리에서 *BATVO.java 파일을 수집합니다.

        Args:
            bat_file_path: BAT.java 파일 경로

        Returns:
            List[str]: 같은 디렉토리에서 발견된 BATVO 파일 경로 목록
        """
        bat_dir = Path(bat_file_path).parent
        batvo_files = []
        for java_file in bat_dir.glob("*.java"):
            if java_file.name.upper().endswith("BATVO.JAVA"):
                batvo_files.append(str(java_file))
        return batvo_files

    def _collect_batvo_candidates(
        self, bat_file: str, batvo_files: List[str]
    ) -> List[str]:
        """
        BATVO 후보 수집 - layer_files + 같은 디렉토리의 *BATVO.java

        Args:
            bat_file: BAT.java 파일 경로
            batvo_files: layer_files에서 수집된 BATVO 파일 목록

        Returns:
            List[str]: 확장된 BATVO 후보 파일 경로 목록
        """
        all_candidates = super()._collect_batvo_candidates(bat_file, batvo_files)

        same_dir_batvos = self._find_batvo_files_in_same_dir(bat_file)
        for f in same_dir_batvos:
            if f not in all_candidates:
                all_candidates.append(f)

        if same_dir_batvos:
            logger.debug(
                f"BNK BATVO 후보 확장: layer={len(batvo_files)}, "
                f"같은디렉토리={len(same_dir_batvos)}, "
                f"총={len(all_candidates)}"
            )

        return all_candidates
