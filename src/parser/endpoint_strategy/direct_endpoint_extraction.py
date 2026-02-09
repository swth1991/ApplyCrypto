from typing import List, Optional

from models.endpoint import Endpoint
from models.method import Method
from parser.java_ast_parser import ClassInfo
from .spring_mvc_endpoint_extraction import SpringMvcEndpointExtraction

class DirectEndpointExtraction(SpringMvcEndpointExtraction):
    LAYER_PATTERNS = {
        "Controller": ["Controller", "RestController", "WebController", "Tasklet", "Resource"],
        "Service": ["Service", "ServiceImpl", "Biz"],
        "Repository": [
            "Repository",
            "JpaRepository",
            "CrudRepository",
            "DAO",
            "Dao",
            "JdbcDao",
            "JdbcTemplateDao",
        ],
        "Mapper": ["Mapper", "MyBatisMapper", "SqlMapper"],
        "Entity": ["Entity", "Domain", "Model", "POJO"],
    }

    def extract_endpoints_from_classes(
        self, classes: List[ClassInfo]
    ) -> List[Endpoint]:
        """
        클래스 목록에서 모든 엔드포인트를 추출합니다.

        Args:
            classes: 클래스 정보 목록

        Returns:
            List[Endpoint]: 추출된 엔드포인트 목록
        """
        endpoints = []

        for cls in classes:
            # 클래스 레벨 경로 추출
            class_path = self.get_class_level_path(cls)

            # 메서드 레벨 엔드포인트 식별
            for method in cls.methods:
                endpoint = self.extract_endpoint(cls, method, class_path)
                if endpoint:
                    endpoints.append(endpoint)
                else:
                    batch_endpoint = self.extract_endpoint_for_batch(cls, method, class_path)
                    if batch_endpoint:
                        endpoints.append(batch_endpoint)

        return endpoints

    def extract_endpoint_for_batch(self, cls: ClassInfo, method: Method, class_path: str) -> Optional[Endpoint]:
        # batch endpoint has following features
        # ends with "Tasklet" and methodname is "run"
        if not cls.name.endswith("Tasklet"):
            return None

        if method.name != "run":
            return None

        # for batch
        path = cls.name
        http_method = "BATCH"
        method_signature = f"{cls.name}.{method.name}"

        return Endpoint(
            path=path,
            http_method=http_method,
            method_signature=method_signature,
            class_name=cls.name,
            method_name=method.name,
            file_path=cls.file_path,
        )