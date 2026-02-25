from config.config_manager import Configuration
from modifier.code_generator.base_code_generator import BaseCodeGenerator
from modifier.context_generator.base_context_generator import BaseContextGenerator


class ContextGeneratorFactory:
    """
    Factory for creating ContextGenerator instances.
    """

    @staticmethod
    def create(
        config: Configuration, code_generator: BaseCodeGenerator
    ) -> BaseContextGenerator:
        """
        Creates a ContextGenerator instance.

        Args:
            config: Configuration object.
            code_generator: CodeGenerator instance.

        Returns:
            BaseContextGenerator: An instance of ContextGenerator.
        """
        if config.sql_wrapping_type == "jdbc_banka":
            from modifier.context_generator.anyframe_banka_context_generator import (
                AnyframeBankaContextGenerator,
            )

            return AnyframeBankaContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "jdbc":
            from modifier.context_generator.jdbc_context_generator import JdbcContextGenerator

            return JdbcContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "mybatis":
            if config.modification_type == "TypeHandler":
                from modifier.context_generator.typehandler_context_generator import TypehandlerContextGenerator

                return TypehandlerContextGenerator(config, code_generator)
            else:
                from modifier.context_generator.mybatis_context_generator import MybatisContextGenerator

                return MybatisContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "mybatis_ccs":
            from modifier.context_generator.mybatis_ccs_context_generator import MybatisCCSContextGenerator

            # mybatis_ccs는 CCS 레이어명(ctl, svcimpl, dqm)을 사용
            return MybatisCCSContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "mybatis_ccs_batch":
            from modifier.context_generator.mybatis_ccs_batch_context_generator import MybatisCCSBatchContextGenerator

            # mybatis_ccs_batch는 CCS 배치 레이어명(bat, batvo)을 사용
            return MybatisCCSBatchContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "ccs_batch":
            from modifier.context_generator.ccs_batch_context_generator import CCSBatchContextGenerator

            # ccs_batch는 CCS 배치 레이어명(bat, batvo)을 사용
            return CCSBatchContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "bnk_batch":
            from modifier.context_generator.bnk_batch_context_generator import BNKBatchContextGenerator

            # bnk_batch는 BNK 배치 레이어명(bat, batvo)을 사용, 같은 디렉토리 BATVO 지원
            return BNKBatchContextGenerator(config, code_generator)

        from modifier.context_generator.per_layer_context_generator import PerLayerContextGenerator

        return PerLayerContextGenerator(config, code_generator)
