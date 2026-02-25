import unittest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
from typing import List

# Add src to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
src_dir = project_root / "src"
sys.path.append(str(src_dir))

from config.config_manager import Configuration
from models.table_access_info import TableAccessInfo
from models.modification_context import ModificationContext
from modifier.code_generator.base_code_generator import BaseCodeGenerator
from modifier.context_generator.jdbc_context_generator import JdbcContextGenerator
from modifier.context_generator.mybatis_context_generator import MybatisContextGenerator


class TestContextGenerators(unittest.TestCase):

    def setUp(self):
        # Common usage basic mock config
        self.mock_config = MagicMock(spec=Configuration)
        self.mock_config.target_project = "/workspace/gam-pjt"
        self.mock_config.max_tokens_per_batch = 10000

        self.mock_code_generator = MagicMock(spec=BaseCodeGenerator)
        self.mock_code_generator.calculate_token_size.return_value = 10
        self.mock_code_generator.create_prompt.return_value = "Prompt"

    def _mock_create_batches(self, file_paths, table_name, columns, layer="", context_files=None):
        """create_batches를 mock하여 파일 I/O 없이 ModificationContext를 반환"""
        if not file_paths:
            return []
        return [ModificationContext(
            file_paths=file_paths,
            table_name=table_name,
            columns=columns,
            file_count=len(file_paths),
            layer=layer,
            context_files=context_files or [],
        )]

    def test_jdbc_context_generator(self):
        """JDBC Context Generator 그룹핑 로직 테스트

        biz, svc 레이어 파일을 keyword 디렉토리 기준으로 그룹화하는지 검증합니다.
        forward-slash 경로 사용 (cross-platform 호환).
        """
        print("\nStarting JDBC Context Generator Test...")

        generator = JdbcContextGenerator(self.mock_config, self.mock_code_generator)

        # Forward-slash 경로 사용 (Linux/Windows 모두 Path로 파싱 가능)
        layer_files = {
            "Repository": [
                "/workspace/gam-pjt/src/main/java/sli/gam/bc/comm/dao/dem/dvo/TGAH00017DVO.java"
            ],
            "dem_daq": [
                "/workspace/gam-pjt/src/main/java/sli/gam/bc/comm/dao/dem/TGAH00017DEM.java"
            ],
            "biz": [
                "/workspace/gam-pjt/src/main/java/sli/gam/bc/comm/biz/BCGaPesnInfoInqrBIZ.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bz/mng/biz/BZMngSalesMngBIZ.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bz/mnger/biz/BZMngerInvwBIZ.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/tgt/biz/TGTrgtBrncBIZ.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/tgt/biz/TGTrgtFpBIZ.java"
            ],
            "svc": [
                "/workspace/gam-pjt/src/main/java/sli/gam/bc/comm/svc/IBCGaPesnInqrSVC.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bc/comm/svc/impl/IBCGaPesnInqrSVCImpl.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bz/mng/svc/IBZMngSalesMngSVC.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bz/mng/svc/impl/IBZMngSalesMngSVCImpl.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bz/mnger/svc/IBZMngerInvwSVC.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/bz/mnger/svc/impl/IBZMngerInvwSVCImpl.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/tgt/svc/ITGTrgtBrncSVC.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/tgt/svc/ITGTrgtFpSVC.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/tgt/svc/impl/ITGTrgtBrncSVCImpl.java",
                "/workspace/gam-pjt/src/main/java/sli/gam/tgt/svc/impl/ITGTrgtFpSVCImpl.java"
            ]
        }

        table_access_info = TableAccessInfo(
            table_name="TEST_TABLE",
            columns=[],
            access_files=[],
            query_type="SELECT",
            layer_files=layer_files
        )

        with patch.object(generator, 'create_batches', side_effect=self._mock_create_batches):
            contexts = generator.generate(
                layer_files=table_access_info.layer_files,
                table_name=table_access_info.table_name,
                columns=table_access_info.columns,
            )

        print(f"Generated {len(contexts)} contexts.")

        found_layers = {}
        for ctx in contexts:
            found_layers[ctx.layer] = ctx.file_count
            print(f"Context Layer: {ctx.layer}, File Count: {ctx.file_count}")

        expected_counts = {
            "Repository": 1,
            "dem_daq": 1,
            "comm": 3,
            "mng": 3,
            "mnger": 3,
            "tgt": 6
        }

        for layer, expected in expected_counts.items():
            self.assertIn(layer, found_layers, f"Missing layer '{layer}'")
            self.assertEqual(found_layers[layer], expected, f"Layer '{layer}' count mismatch. Expected {expected}, got {found_layers[layer]}.")

        print("JDBC Context Generator Test Passed.")


    def test_mybatis_context_generator(self):
        """Mybatis Context Generator 그룹핑 로직 테스트

        Controller 파일의 import 분석을 통해 관련 Service/Repository 파일을 그룹화하는지 검증합니다.
        실제 파일 I/O 없이 JavaASTParser를 mock하여 테스트합니다.
        """
        print("\nStarting Mybatis Context Generator Test...")

        self.mock_config.target_project = "/workspace/PrimusCPS_Eai"

        generator = MybatisContextGenerator(self.mock_config, self.mock_code_generator)

        # 테스트 데이터: forward-slash 경로
        controller_files = [
            "/workspace/PrimusCPS_ExternalApi/src/main/java/com/cps/api/point/customers/controller/PntCustomersBankInfoController.java",
        ]
        service_files = [
            "/workspace/PrimusCPS_ExternalApi/src/main/java/com/cps/api/point/customers/service/PntCustomersBankInfoService.java",
            "/workspace/PrimusCPS_ExternalApi/src/main/java/com/cps/api/point/customers/service/PntCustomersBankInfoServiceImpl.java",
        ]
        repository_files = [
            "/workspace/PrimusCPS_ExternalApi/src/main/java/com/cps/api/point/customers/dao/PntCustomersBankInfoDao.java",
        ]

        layer_files = {
            "service": service_files,
            "controller": controller_files,
            "repository": repository_files,
        }

        table_access_info = TableAccessInfo(
            table_name="TEST_TABLE",
            columns=[{"name": "COL1", "new_column": False}],
            access_files=[],
            query_type="SELECT",
            layer_files=layer_files
        )

        # Mock JavaASTParser를 생성하여 파일 파싱 대신 mock class info 반환
        mock_tree = MagicMock()

        @dataclass
        class MockClassInfo:
            name: str = "PntCustomersBankInfoController"
            access_modifier: str = "public"
            imports: List[str] = field(default_factory=lambda: [
                "com.cps.api.point.customers.service.PntCustomersBankInfoService",
                "com.cps.api.point.customers.dao.PntCustomersBankInfoDao",
            ])
            annotations: List[str] = field(default_factory=lambda: ["RestController"])
            methods: List = field(default_factory=list)
            fields: List = field(default_factory=list)

        mock_class_info = MockClassInfo()

        with patch.object(generator, 'create_batches', side_effect=self._mock_create_batches), \
             patch('modifier.context_generator.mybatis_context_generator.JavaASTParser') as MockParser:

            parser_instance = MockParser.return_value
            parser_instance.parse_file.return_value = (mock_tree, None)
            parser_instance.extract_class_info.return_value = [mock_class_info]

            contexts = generator.generate(
                layer_files=table_access_info.layer_files,
                table_name=table_access_info.table_name,
                columns=table_access_info.columns,
            )

        print(f"Generated {len(contexts)} contexts.")

        for ctx in contexts:
            print(f"File Count: {ctx.file_count}")
            for file_path in ctx.file_paths:
                filename = Path(file_path).name
                print(f" - {filename}")
            print("-" * 30)

        # MybatisContextGenerator는 controller + import에 매칭되는 service를 하나의 그룹으로 묶음
        # Note: repository_files는 vo.java로 끝나는 것만 포함되므로 Dao는 제외됨
        # Note: _match_import_to_file_path는 exact match 우선이므로 Service는 매칭되지만 ServiceImpl은 제외
        self.assertTrue(len(contexts) >= 1, "At least 1 context should be generated.")

        # Controller + exact match된 Service가 포함되어야 함
        all_files = []
        for ctx in contexts:
            all_files.extend([Path(f).name for f in ctx.file_paths])

        self.assertIn("PntCustomersBankInfoController.java", all_files)
        self.assertIn("PntCustomersBankInfoService.java", all_files)

        print("Mybatis Context Generator Test Passed.")

if __name__ == "__main__":
    unittest.main()
