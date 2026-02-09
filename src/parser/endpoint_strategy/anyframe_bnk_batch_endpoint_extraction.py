"""
Anyframe BNK Batch Endpoint Extraction Strategy

BNK 배치 프로그램의 엔드포인트(진입점)를 추출하는 전략 클래스입니다.

특징:
    - 엔드포인트 조건: 클래스명이 *BAT로 끝나고 execute 메서드가 존재
    - HTTP endpoint가 아닌 배치 Job의 진입점으로 처리
    - 레이어 분류: BAT, BATVO
"""

from .batch_endpoint_extraction_base import BatchEndpointExtractionBase


class AnyframeBNKBatchEndpointExtraction(BatchEndpointExtractionBase):
    """
    BNK 배치 프로그램 엔드포인트 추출 전략

    BatchEndpointExtractionBase의 기본 동작을 그대로 사용합니다.
    BNK 고유 로직이 필요할 경우 클래스 속성이나 메서드를 오버라이드합니다.
    """

    pass
