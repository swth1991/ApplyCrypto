"""
Endpoint Extraction Strategy Factory

framework_type에 따라 적절한 EndpointExtractionStrategy 인스턴스를 생성하는 Factory 클래스입니다.
"""

from typing import Optional

from parser.java_ast_parser import JavaASTParser
from persistence.cache_manager import CacheManager


from config.config_manager import Configuration
from .endpoint_extraction_strategy import EndpointExtractionStrategy


class EndpointExtractionStrategyFactory:
    """EndpointExtractionStrategy 생성을 위한 팩토리 클래스"""

    @staticmethod
    def create(
        config: Configuration,
        java_parser: Optional[JavaASTParser] = None,
        cache_manager: Optional[CacheManager] = None,
    ) -> EndpointExtractionStrategy:
        """
        framework_type에 따라 적절한 EndpointExtractionStrategy 인스턴스를 생성합니다.

        Args:
            config: 설정 객체
            java_parser: Java AST 파서 (선택적)
            cache_manager: 캐시 매니저 (선택적)

        Returns:
            EndpointExtractionStrategy: 생성된 Strategy 인스턴스

        Raises:
            ValueError: 지원하지 않는 framework_type인 경우
        """
        framework_type = config.framework_type

        if framework_type == "SpringMVC":
            from .spring_mvc_endpoint_extraction import SpringMVCEndpointExtraction

            return SpringMVCEndpointExtraction(java_parser=java_parser, cache_manager=cache_manager)

        elif framework_type == "SpringDirect":
            from .direct_endpoint_extraction import DirectEndpointExtraction

            return DirectEndpointExtraction(
                java_parser=java_parser, cache_manager=cache_manager
            )

        elif framework_type == "SpringDigitalChannel":
            from .digital_channel_batch_endpoint_extractor import DigitalChannelBatchEndpointExtractor

            return DigitalChannelBatchEndpointExtractor(
                java_parser=java_parser, cache_manager=cache_manager
            )

        elif framework_type == "Anyframe":
            from .anyframe_endpoint_extraction import AnyframeEndpointExtraction

            return AnyframeEndpointExtraction(java_parser=java_parser, cache_manager=cache_manager)

        elif framework_type == "AnyframeSarangon":
            from .anyframe_sarangon_endpoint_extraction import AnyframeSarangOnEndpointExtraction

            return AnyframeSarangOnEndpointExtraction(java_parser=java_parser, cache_manager=cache_manager)

        elif framework_type == "AnyframeSarangonBatch":
            from .anyframe_bat_etc_endpoint_extraction import AnyframeBatEtcEndpointExtraction

            return AnyframeBatEtcEndpointExtraction(java_parser=java_parser, cache_manager=cache_manager)
            
        elif framework_type == "AnyframeOld":
            # TODO: 추후 구현
            raise NotImplementedError(
                f"framework_type '{framework_type}'는 아직 구현되지 않았습니다."
            )

        elif framework_type == "AnyframeEtc":
            # TODO: 추후 구현
            raise NotImplementedError(
                f"framework_type '{framework_type}'는 아직 구현되지 않았습니다."
            )

        elif framework_type == "AnyframeCCS":
            from .anyframe_ccs_endpoint_extraction import AnyframeCCSEndpointExtraction

            return AnyframeCCSEndpointExtraction(java_parser=java_parser, cache_manager=cache_manager)

        elif framework_type == "SpringBatQrts":
            # TODO: 추후 구현
            raise NotImplementedError(
                f"framework_type '{framework_type}'는 아직 구현되지 않았습니다."
            )

        elif framework_type == "AnyframeBatSarangOn":
            # TODO: 추후 구현
            raise NotImplementedError(
                f"framework_type '{framework_type}'는 아직 구현되지 않았습니다."
            )

        elif framework_type == "AnyframeBatEtc":
            # TODO: 추후 구현
            raise NotImplementedError(
                f"framework_type '{framework_type}'는 아직 구현되지 않았습니다."
            )

        elif framework_type == "anyframe_ccs_batch":
            from .anyframe_ccs_batch_endpoint_extraction import (
                AnyframeCCSBatchEndpointExtraction,
            )

            return AnyframeCCSBatchEndpointExtraction(
                java_parser=java_parser, cache_manager=cache_manager
            )

        else:
            raise ValueError(
                f"지원하지 않는 framework_type: {framework_type}. "
                f"가능한 값: SpringMVC, SpringDirect, SpringDigitalChannel, "
                f"Anyframe, AnyframeSarangOn, AnyframeSarangonBatch, "
                f"AnyframeOld, AnyframeEtc, AnyframeCCS, "
                f"SpringBatQrts, AnyframeBatSarangOn, AnyframeBatEtc, "
                f"anyframe_ccs_batch"
            )

