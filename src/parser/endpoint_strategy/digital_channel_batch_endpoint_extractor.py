from typing import List, Optional

from models.endpoint import Endpoint
from models.method import Method
from parser.java_ast_parser import ClassInfo
from .endpoint_extraction_strategy import EndpointExtractionStrategy


class DigitalChannelBatchEndpointExtractor(EndpointExtractionStrategy):

    LAYER_PATTERNS = {
        "Controller": ["Tasklet","Reader", "Writer"],
        "Service": ["Service"],
        "Repository": ["Repository", "Dao", "Mapper"],
        "VO": ["Vo", "DaoModel"]
    }

    def extract_endpoints_from_classes(self, classes: List[ClassInfo]) -> List[Endpoint]:
        endpoints = []

        for cls in classes:
            # 클래스 레벨 경로 추출
            class_path = self.get_class_level_path(cls)

            # 메서드 레벨 엔드포인트 식별
            for method in cls.methods:
                endpoint = self.extract_endpoint(cls, method, class_path)
                if endpoint:
                    endpoints.append(endpoint)

        return endpoints

    def extract_endpoint(
        self, cls: ClassInfo, method: Method, class_path: str
    ) -> Optional[Endpoint]:
        """
        Reader/Writer 클래스에서 엔드포인트(read/write 메서드) 추출
        """
        # Reader 클래스 처리 (*Reader.java)
        if cls.name.endswith("Reader") and method.name == "read":
            return Endpoint(
                path=class_path,
                http_method="BATCH",
                method_signature=f"{cls.name}.{method.name}",
                class_name=cls.name,
                method_name=method.name,
                file_path=cls.file_path,
            )

        # Writer 클래스 처리 (*Writer.java)
        elif cls.name.endswith("Writer") and method.name == "write":
            return Endpoint(
                path=class_path,
                http_method="BATCH",
                method_signature=f"{cls.name}.{method.name}",
                class_name=cls.name,
                method_name=method.name,
                file_path=cls.file_path,
            )

        return None

    def get_class_level_path(self, cls: ClassInfo) -> str:
        """클래스 레벨 경로 추출 (Batch의 경우 빈 문자열 또는 Job 이름 등)"""
        return ""

    def extract_path_from_annotation(self, annotation: str) -> Optional[str]:
        """어노테이션에서 path 추출 (Batch는 사용 안 함)"""
        return None

    def extract_http_method_from_annotation(self, annotation: str) -> Optional[str]:
        """어노테이션에서 HTTP 메서드 추출 (Batch는 사용 안 함)"""
        return None

    def classify_layer(self, cls: ClassInfo, method: Method) -> str:
        """레이어 분류"""
        for layer, patterns in self.LAYER_PATTERNS.items():
            for pattern in patterns:
                if cls.name.endswith(pattern):
                    return layer
        return "Unknown"