"""
Cache Manager 모듈

분석 결과를 캐싱하여 재분석 시 성능을 향상시키는 캐시 관리자입니다.
"""

import hashlib
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# tree_sitter.Tree 타입 확인을 위한 임포트 (선택적)
try:
    from tree_sitter import Tree as TreeSitterTree

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    TreeSitterTree = None


class CacheManager:
    """
    캐시 관리자 클래스

    메모리 캐시와 디스크 캐시를 지원하며, 캐시 만료 정책을 구현합니다.
    """

    def __init__(
        self,
        cache_dir: Path,
        memory_cache_size: int = -1,
        cache_expiry_hours: int = -1,
    ):
        """
        CacheManager 초기화

        Args:
            cache_dir: 캐시 디렉터리 경로
            memory_cache_size: 메모리 캐시 최대 크기 (항목 수). 음수면 제한 없음.
            cache_expiry_hours: 캐시 만료 시간 (시간). 음수면 만료 없음.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir = Path(cache_dir)
        # self.memory_cache removed as requested
        # self.memory_cache_size removed as requested
        
        if cache_expiry_hours < 0:
            self.cache_expiry = None
        else:
            self.cache_expiry = timedelta(hours=cache_expiry_hours)

        self.logger = logging.getLogger(__name__)

        # 캐시 디렉터리 생성
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, file_path: Path) -> str:
        """
        파일 경로와 수정 시간을 기반으로 캐시 키 생성

        Args:
            file_path: 파일 경로 (Path 객체 또는 문자열)

        Returns:
            str: 캐시 키
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        try:
            stat = file_path.stat()
            # 파일 경로와 수정 시간을 조합하여 해시 생성
            key_data = f"{file_path}:{stat.st_mtime}"
            hash_value = hashlib.md5(key_data.encode()).hexdigest()
            return f"{file_path.name}__{hash_value}"
        except OSError:
            # 파일이 없거나 접근 불가능한 경우 경로만 사용
            hash_value = hashlib.md5(str(file_path).encode()).hexdigest()
            return f"{file_path.name}__{hash_value}"

    def _get_cache_file_path(self, cache_key: str, namespace: str = None) -> Path:
        """캐시 파일 경로 생성"""
        if namespace:
            directory = self.cache_dir / namespace
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
            return directory / f"{cache_key}.cache"
        return self.cache_dir / f"{cache_key}.cache"

    def get_cached_result(self, file_path: Path, namespace: str = None) -> Optional[Any]:
        """
        캐시된 결과 조회

        Args:
            file_path: 원본 파일 경로 (Path 객체 또는 문자열)

        Returns:
            캐시된 결과 (없으면 None)
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        cache_key = self._get_cache_key(file_path)

        # 디스크 캐시 확인
        cache_file = self._get_cache_file_path(cache_key, namespace=namespace)
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    cache_entry = pickle.load(f)

                if self._is_cache_valid(cache_entry, file_path):
                    self.logger.debug(f"디스크 캐시에서 조회: {file_path}")
                    return cache_entry["data"]
                else:
                    # 만료된 캐시 파일 삭제
                    cache_file.unlink()
            except (pickle.UnpicklingError, EOFError) as e:
                # 손상된 캐시 파일은 삭제하고 계속 진행
                self.logger.warning(f"손상된 캐시 파일 삭제: {cache_file} - {e}")
                try:
                    cache_file.unlink()
                except Exception:
                    pass
            except Exception as e:
                self.logger.warning(f"캐시 파일 로드 실패: {e}")

        return None

    def set_cached_result(self, file_path: Path, data: Any, namespace: str = None) -> None:
        """
        결과를 캐시에 저장

        Args:
            file_path: 원본 파일 경로 (Path 객체 또는 문자열)
            data: 캐시할 데이터
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        cache_key = self._get_cache_key(file_path)
        cache_entry = {
            "data": data,
            "file_path": str(file_path),
            "cached_time": datetime.now(),
            "file_mtime": file_path.stat().st_mtime if file_path.exists() else 0,
        }

        # 디스크 캐시에 저장 (tree_sitter.Tree 객체는 pickle 불가능하므로 건너뜀)
        # Tree 객체인지 확인 (tree_sitter.Tree는 pickle로 직렬화할 수 없음)
        is_tree_object = False
        if HAS_TREE_SITTER and TreeSitterTree is not None:
            is_tree_object = isinstance(data, TreeSitterTree)
        else:
            # tree_sitter가 없거나 타입 확인이 불가능한 경우 문자열로 확인
            try:
                if hasattr(data, "__class__") and "tree_sitter" in str(type(data)):
                    is_tree_object = True
            except Exception:
                pass

        if is_tree_object:
            # Tree 객체는 디스크 저장 불가 - 메모리 캐시 제거됨
            self.logger.debug(f"Tree 객체는 디스크 저장 불가: {file_path}")
            return

        # 일반 데이터는 디스크 캐시에 저장
        cache_file = self._get_cache_file_path(cache_key, namespace=namespace)
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(cache_entry, f)
            self.logger.debug(f"캐시 저장 완료: {file_path}")
        except (pickle.PickleError, TypeError) as e:
            # pickle 불가능한 객체는 저장 불가
            self.logger.debug(
                f"pickle 불가능한 객체는 저장 불가: {file_path} - {e}"
            )
        except Exception as e:
            self.logger.warning(f"캐시 파일 저장 실패: {e}")



    def _is_cache_valid(self, cache_entry: Dict[str, Any], file_path: Path) -> bool:
        """
        캐시가 유효한지 확인

        Args:
            cache_entry: 캐시 항목
            file_path: 원본 파일 경로 (Path 객체 또는 문자열)

        Returns:
            bool: 캐시가 유효하면 True
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        # 파일이 존재하지 않으면 캐시 무효
        if not file_path.exists():
            return False

        # 파일 수정 시간 확인
        current_mtime = file_path.stat().st_mtime
        cached_mtime = cache_entry.get("file_mtime", 0)
        if current_mtime != cached_mtime:
            return False

        # 캐시 만료 시간 확인
        cached_time = cache_entry.get("cached_time")
        if cached_time:
            if isinstance(cached_time, str):
                cached_time = datetime.fromisoformat(cached_time)
            if self.cache_expiry is not None and datetime.now() - cached_time > self.cache_expiry:
                return False

        return True

    def invalidate_cache(self, file_path: Path, namespace: str = None) -> None:
        """
        특정 파일의 캐시 무효화

        Args:
            file_path: 캐시를 무효화할 파일 경로 (Path 객체 또는 문자열)
            namespace: 캐시 네임스페이스 (선택적)
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        cache_key = self._get_cache_key(file_path)

        # 디스크 캐시 파일 삭제
        cache_file = self._get_cache_file_path(cache_key, namespace=namespace)
        if cache_file.exists():
            try:
                cache_file.unlink()
                self.logger.debug(f"캐시 무효화: {file_path}")
            except Exception as e:
                self.logger.warning(f"캐시 파일 삭제 실패: {e}")

    def clear_cache(self) -> None:
        """모든 캐시 삭제"""
        # 메모리 캐시 삭제 로직 제거됨

        # 디스크 캐시 파일 삭제
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            self.logger.info("모든 캐시 삭제 완료")
        except Exception as e:
            self.logger.warning(f"캐시 파일 삭제 중 오류: {e}")
