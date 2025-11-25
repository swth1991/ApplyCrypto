# ApplyCrypto

Java Spring Boot 프로젝트 암호화 자동 적용 도구

## 개요

ApplyCrypto는 Java Spring Boot 기반 레거시 시스템에서 민감한 개인정보를 데이터베이스에 암호화하여 저장하도록 소스 코드를 자동으로 분석하고 수정하는 AI 기반 개발 도구입니다.

## 설치

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
source venv/bin/activate  # Linux/macOS
# 또는
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

## 개발 환경 설정

```bash
# 개발 의존성 포함 설치
pip install -e ".[dev]"
```

## 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 커버리지 포함 테스트
pytest --cov=src --cov-report=html
```

## 프로젝트 구조

```
samsung-life/
├── src/
│   ├── cli/
│   │   ├── __init__.py
│   │   └── cli_controller.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── config_manager.py
│   ├── collector/
│   │   ├── __init__.py
│   │   └── source_file_collector.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── source_file.py
│   └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_cli_controller.py
│   ├── test_config_manager.py
│   └── test_source_file_collector.py
├── main.py              # CLI 진입점
├── config.example.json  # 예제 설정 파일
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 사용 예시

### CLI 사용

```bash
# 프로젝트 분석
python main.py analyze --config config.json

# 모든 소스 파일 목록 조회
python main.py list --all

# 테이블별 접근 파일 목록 조회
python main.py list --db

# REST API 엔드포인트 목록 조회
python main.py list --endpoint

# 특정 엔드포인트의 호출 그래프 조회
python main.py list --callgraph /api/employee/{id}

# 파일 수정 (미리보기)
python main.py modify --config config.json --dry-run

# 파일 수정 (실제 수정)
python main.py modify --config config.json
```

### Python API 사용

```python
from src.config import ConfigurationManager

# 설정 파일 로드
manager = ConfigurationManager("config.json")

# 설정값 접근
project_path = manager.project_path
file_types = manager.source_file_types
sql_type = manager.sql_wrapping_type
tables = manager.access_tables
```

