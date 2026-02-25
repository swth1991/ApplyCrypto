"""
CCS Batch Context Generator

CCS 배치 프로그램용 Context Generator입니다.
BatchBaseContextGenerator의 기본 동작을 그대로 사용합니다.

특징:
    - 수정 대상 (file_paths): BAT.java
    - 참조용 context (context_files): BATVO.java (import 기반 필터링) + XXX_SQL.xml
    - BATVO 수집: layer_files의 batvo 파일만 사용 (기본 동작)
"""

from config.config_manager import Configuration

from .batch_base_context_generator import BatchBaseContextGenerator


class CCSBatchContextGenerator(BatchBaseContextGenerator):
    """
    CCS 배치 프로그램용 Context Generator

    BatchBaseContextGenerator의 기본 동작을 그대로 사용합니다.
    CCS 고유 로직이 필요할 경우 메서드를 오버라이드합니다.
    """

    def __init__(self, config: Configuration, code_generator):
        super().__init__(config, code_generator)
