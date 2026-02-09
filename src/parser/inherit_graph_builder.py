from typing import Dict, List, Optional
from models.inherit_node import InheritNode
from parser.java_ast_parser import ClassInfo

class InheritGraphBuilder:
    """
    상속 관계 그래프 빌더
    
    Java 클래스 간의 상속 관계를 분석하고 상속 맵을 생성합니다.
    """

    def __init__(self, file_to_classes_map: Dict[str, List[ClassInfo]], class_name_to_info: Dict[str, ClassInfo]):
        """
        초기화

        Args:
            file_to_classes_map: 파일 경로 -> 클래스 정보 리스트 매핑
            class_name_to_info: 클래스명 -> 클래스 정보 매핑
        """
        self.file_to_classes_map = file_to_classes_map
        self.class_name_to_info = class_name_to_info

    def get_inheritance_map(self) -> Dict[str, InheritNode]:
        """
        상속 관계 맵 생성

        Returns:
            Dict[str, InheritNode]: 클래스명을 키로 하고 상속 정보를 담은 InheritNode 객체 딕셔너리
        """
        inheritance_map = {}
        
        # file_to_classes_map을 사용하여 모든 파싱된 클래스 순회
        for file_path, classes in self.file_to_classes_map.items():
            for cls in classes:
                simple_name = cls.name
                
                # 중복 클래스 처리 (덮어쓰기)
                inheritance_map[simple_name] = InheritNode(
                    name=simple_name,
                    package=cls.package,
                    superclass=cls.superclass,
                    interfaces=cls.interfaces,
                    file_path=str(cls.file_path)
                )
                
        return inheritance_map

    def get_ancestor_inherit_nodes(self, class_name: str) -> List[InheritNode]:
        """
        주어진 클래스명의 모든 조상 클래스(상위 클래스)의 InheritNode 목록을 반환합니다.
        가장 가까운 부모부터 최상위 부모 순서로 반환합니다.

        Args:
            class_name: 클래스명 (Simple Name)

        Returns:
            List[InheritNode]: 조상 클래스들의 InheritNode 리스트
        """
        ancestors = []
        current_class_name = class_name

        while current_class_name:
            # 현재 클래스 정보 조회
            current_cls_info = self.class_name_to_info.get(current_class_name)
            
            if not current_cls_info:
                break
                
            superclass_name = current_cls_info.superclass
            
            # 상위 클래스가 없거나 Object인 경우 중단
            if not superclass_name or superclass_name == "Object":
                break
                
            # 상위 클래스 정보 조회
            superclass_info = self.class_name_to_info.get(superclass_name)
            
            if superclass_info:
                # InheritNode 생성 및 추가
                inherit_node = InheritNode(
                    name=superclass_info.name,
                    package=superclass_info.package,
                    superclass=superclass_info.superclass,
                    interfaces=superclass_info.interfaces,
                    file_path=str(superclass_info.file_path)
                )
                ancestors.append(inherit_node)
                
                # 다음 순회를 위해 업데이트
                current_class_name = superclass_name
            else:
                # 상위 클래스 정보가 없는 경우 (외부 라이브러리 등) 중단
                break
                
        return ancestors
