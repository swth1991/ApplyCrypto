"""
엔드포인트 분석 공통 유틸리티

CLI와 Report Generator 간 코드 재사용을 위한 공통 함수 모음
"""

from typing import Dict, Optional, List, Any
from models.endpoint import Endpoint


def _is_signature_match(sig1: str, sig2: str) -> bool:
    """
    두 메소드 시그니처가 일치하는지 확인합니다.
    (정확한 매칭 또는 패키지명을 포함한 매칭 지원)
    
    Args:
        sig1: 첫 번째 시그니처
        sig2: 두 번째 시그니처
    """
    if not sig1 or not sig2:
        return False
    if sig1 == sig2:
        return True
    # sig1이 sig2의 fully qualified version인 경우 (예: com.ext.Ctrl.method vs Ctrl.method)
    if sig1.endswith("." + sig2):
        return True
    # sig2가 sig1의 fully qualified version인 경우
    if sig2.endswith("." + sig1):
        return True
    return False


def find_endpoint_in_call_graph(
    method_signature: str,
    call_graph_data: Dict[str, Any],
    return_type: str = "dict",
) -> Optional[Dict[str, Any]]:
    """
    메소드 시그니처에 해당하는 엔드포인트를 Call Graph에서 찾습니다.
    
    CLI의 _list_callgraph에서 사용하던 기존 로직을 그대로 이관했습니다.
    
    Args:
        method_signature: 찾을 메소드 시그니처 (예: "EmpController.addEmpByGet")
        call_graph_data: Call Graph JSON 데이터
        return_type: 반환 타입 - "dict" (경로 문자열), "endpoint" (Endpoint 객체), "full" (전체 정보)
    
    Returns:
        Optional[Dict]: 매칭된 엔드포인트 정보 또는 None
                       return_type에 따라 다른 형식 반환:
                       - "dict": {'path': '...', 'http_method': '...', ...}
                       - "endpoint": Endpoint 객체
                       - "full": 전체 엔드포인트 정보
    
    Example:
        >>> call_graph = load_call_graph('call_graph.json')
        >>> endpoint = find_endpoint_in_call_graph('BookController.listBooks', call_graph)
        >>> if endpoint:
        ...     print(endpoint['path'])
    
    Note:
        현재 구현: 정확한 메소드 시그니처 매칭 및 후방 일치(Endswith) 매칭 지원
    """
    if "endpoints" not in call_graph_data:
        return None
    
    endpoints = call_graph_data.get("endpoints", [])
    
    # Endpoint 객체로 변환
    endpoint_objects = []
    for ep in endpoints:
        if isinstance(ep, dict):
            endpoint_objects.append(Endpoint.from_dict(ep))
        elif isinstance(ep, Endpoint):
            endpoint_objects.append(ep)
    
    # 엔드포인트 매칭
    for ep_obj in endpoint_objects:
        ep_method_sig = ep_obj.method_signature
        
        if _is_signature_match(ep_method_sig, method_signature):
            return _format_endpoint_result(ep_obj, return_type)
    
    return None


def find_all_endpoints_for_method(
    method_signature: str,
    call_graph_data: Dict[str, Any],
    return_type: str = "dict",
) -> List[Dict[str, Any]]:
    """
    메소드 시그니처에 해당하는 모든 엔드포인트를 찾습니다.
    (첫 번째 매칭만 반환하는 find_endpoint_in_call_graph와 다름)
    
    Args:
        method_signature: 찾을 메소드 시그니처
        call_graph_data: Call Graph JSON 데이터
        return_type: 반환 타입 ("dict", "endpoint", "full")
    
    Returns:
        List[Dict]: 매칭된 모든 엔드포인트 목록
    """
    if "endpoints" not in call_graph_data:
        return []
    
    endpoints = call_graph_data.get("endpoints", [])
    matched = []
    
    # Endpoint 객체로 변환
    endpoint_objects = []
    for ep in endpoints:
        if isinstance(ep, dict):
            endpoint_objects.append(Endpoint.from_dict(ep))
        elif isinstance(ep, Endpoint):
            endpoint_objects.append(ep)
    
    # 모든 엔드포인트에서 매칭 찾기
    for ep_obj in endpoint_objects:
        ep_method_sig = ep_obj.method_signature
        
        if _is_signature_match(ep_method_sig, method_signature):
            matched.append(_format_endpoint_result(ep_obj, return_type))
    
    return matched


def find_endpoints_that_call_method(
    method_signature: str,
    call_graph_data: Dict[str, Any],
    return_type: str = "dict",
) -> List[Dict[str, Any]]:
    """
    메소드가 호출되는 모든 엔드포인트를 찾습니다.
    
    call_trees를 역추적해서 이 메소드를 호출하는 엔드포인트들을 찾습니다.
    Service, Mapper, Interceptor 등 직접 엔드포인트가 없는 메소드에 유용합니다.
    
    예시:
        Employee.getDayOfBirth를 찾으면:
        - EmpController.addEmpByGet → GET /api/emps/addEmpByGet ✅
        - EmpController.addEmpByPost → POST /api/emps/addEmpByPost ✅
        - EmployeeController.addEmp → GET /emp/addEmpByGet ✅
        - ... 총 8개의 엔드포인트 반환
    
    Args:
        method_signature: 찾을 메소드 시그니처 (예: "Employee.getDayOfBirth")
        call_graph_data: Call Graph JSON 데이터 (call_trees 포함)
        return_type: 반환 타입 ("dict", "endpoint", "full")
    
    Returns:
        List[Dict]: 이 메소드를 호출하는 모든 엔드포인트 목록 (중복 제거)
    """
    matched_endpoints = {}  # endpoint_method_sig를 key로 중복 제거
    
    call_trees = call_graph_data.get("call_trees", [])
    if not call_trees:
        return []
    
    # Endpoint 객체 캐시
    endpoint_objects = {}
    if "endpoints" in call_graph_data:
        for ep in call_graph_data["endpoints"]:
            if isinstance(ep, dict):
                ep_obj = Endpoint.from_dict(ep)
            else:
                ep_obj = ep
            endpoint_objects[ep_obj.method_signature] = ep_obj
    
    def find_method_in_tree(node: Dict[str, Any], target_method: str) -> bool:
        """재귀적으로 트리에서 메소드 시그니처를 찾습니다."""
        method_sig = node.get("method_signature", "")
        
        # 시그니처 매칭 (정확히 일치하거나 qualified match)
        if _is_signature_match(method_sig, target_method):
            return True
        
        # 자식 노드 재귀 탐색
        for child in node.get("children", []):
            if find_method_in_tree(child, target_method):
                return True
        
        return False
    
    # 모든 call_tree에서 해당 메소드를 호출하는 엔드포인트 찾기
    for tree in call_trees:
        endpoint_info = tree.get("endpoint", {})
        endpoint_method_sig = endpoint_info.get("method_signature", "")
        
        # 이 call_tree가 대상 메소드를 호출하는지 확인
        if find_method_in_tree(tree, method_signature):
            # 이 엔드포인트를 결과에 추가
            if endpoint_method_sig and endpoint_method_sig not in matched_endpoints:
                if endpoint_method_sig in endpoint_objects:
                    ep_obj = endpoint_objects[endpoint_method_sig]
                    matched_endpoints[endpoint_method_sig] = _format_endpoint_result(
                        ep_obj, return_type
                    )
    
    return list(matched_endpoints.values())


def _format_endpoint_result(
    endpoint_obj: Endpoint,
    return_type: str,
) -> Dict[str, Any]:
    """
    Endpoint 객체를 요청된 형식으로 변환합니다.
    
    Args:
        endpoint_obj: Endpoint 객체
        return_type: 반환 타입 ("dict", "endpoint", "full")
    
    Returns:
        Dict: 포맷된 엔드포인트 정보
    """
    if return_type == "endpoint":
        return endpoint_obj
    elif return_type == "full":
        return endpoint_obj.to_dict() if hasattr(endpoint_obj, "to_dict") else vars(endpoint_obj)
    else:  # "dict" (기본값)
        return {
            "path": endpoint_obj.path,
            "http_method": endpoint_obj.http_method,
            "method_signature": endpoint_obj.method_signature,
            "class_name": endpoint_obj.class_name,
        }
