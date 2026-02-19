# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ApplyCrypto는 Java Spring Boot 레거시 시스템에서 민감한 개인정보를 암호화/복호화하도록 소스 코드를 자동으로 분석하고 수정하는 AI 기반 도구입니다. 정적 코드 분석, 콜 그래프 순회, LLM 기반 코드 생성을 사용합니다.

## Common Commands

### Running the Tool
```bash
# Analyze project (collect source files, build call graph, identify DB access patterns)
python main.py analyze --config config.json

# List analysis results
python main.py list --all          # All source files
python main.py list --db           # Table access information
python main.py list --endpoint     # REST API endpoints
python main.py list --callgraph EmpController.login  # Method call chain

# Modify code (insert encryption/decryption logic)
python main.py modify --config config.json --dry-run  # Preview only
python main.py modify --config config.json            # Apply changes

# Clear analysis results
python main.py clear  # Remove cached analysis data

# Launch Streamlit UI
python run_ui.py
```

### Development Commands
```bash
pytest                                      # Run all tests
pytest tests/test_db_access_analyzer.py     # Run specific test
pytest --cov=src --cov-report=html          # Tests with coverage

# Linting (run before commit)
./scripts/lint.ps1                          # Windows
isort . && ruff format && ruff check --fix  # Manual
```

### Environment Variables
Create a `.env` file with LLM provider credentials:
```
WATSONX_API_URL=https://us-south.ml.cloud.ibm.com
WATSONX_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
```

**Note:** Python 3.13 이상이 필요합니다. 가상환경 생성 예시:
```bash
python3.13 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## Architecture Overview

### Layered Architecture Flow
```
CLI Layer → Configuration → Collection → Parsing → Analysis → Modification → Persistence
```

1. **CLI Layer** (`src/cli/`) → Entry point, orchestrates workflow
2. **Configuration Layer** (`src/config/`) → JSON config with Pydantic validation
3. **Collection Layer** (`src/collector/`) → Recursive source file collection
4. **Parsing Layer** (`src/parser/`) → Java AST (tree-sitter), XML Mappers, Call Graph (NetworkX)
5. **Analysis Layer** (`src/analyzer/`) → DB access patterns via call graph traversal
6. **Modification Layer** (`src/modifier/`) → LLM-based code generation and patching
7. **LLM Layer** (`src/modifier/llm/`) → Provider abstraction (WatsonX, OpenAI, Claude)
8. **Persistence Layer** (`src/persistence/`) → JSON serialization and caching
9. **Generator Layer** (`src/generator/`) → Report generation and output formatting

### Key Design Patterns

**Strategy Pattern** - 새로운 프레임워크나 SQL 타입 추가 시 확장:
- `LLMProvider`: LLM 프로바이더 추상화 (`src/modifier/llm/`)
- `EndpointExtractionStrategy`: 프레임워크별 엔드포인트 추출 (`src/parser/endpoint_strategy/`)
- `SQLExtractor`: SQL 래핑 타입별 추출 전략 (`src/analyzer/sql_extractors/`)
  - `MyBatisSQLExtractor`, `MyBatisCCSSQLExtractor`, `CCSBatchSQLExtractor`, `BNKBatchSQLExtractor`
  - `JdbcSQLExtractor`, `JpaSQLExtractor`
  - `AnyframeJdbcSQLExtractor`, `AnyframeJdbcBatSQLExtractor`
- `BaseCodeGenerator`: 코드 생성 전략 (`src/modifier/code_generator/`)
  - `ThreeStepBankaCodeGenerator`: BNK 온라인 전용 (Phase 1 VO 제외, Phase 2 BIZ 메서드만 추출)
- `BaseMultiStepCodeGenerator`: 다단계 코드 생성 베이스 (`src/modifier/code_generator/multi_step_base/`)
- `ContextGenerator`: 컨텍스트 생성 전략 (`src/modifier/context_generator/`)
  - `AnyframeContextGenerator`: import 기반 파일 그룹 생성 (`jdbc`, `jpa`)
  - `AnyframeBankaContextGenerator`: call_stack 기반 파일 그룹 생성 (`jdbc_banka`), `BaseContextGenerator` 직접 상속

**Factory Pattern** - 설정 기반 전략 생성:
- `LLMFactory`, `EndpointExtractionStrategyFactory`, `SQLExtractorFactory`
- `CodeGeneratorFactory`, `ContextGeneratorFactory`

### Configuration Schema

The `config.json` file drives the entire workflow. Key fields:

| Field | Description |
|-------|-------------|
| `framework_type` | `SpringMVC`, `AnyframeSarangOn`, `AnyframeCCS`, `anyframe_ccs_batch`, `anyframe_banka`, `BatBanka` 등 |
| `sql_wrapping_type` | `mybatis`, `mybatis_ccs`, `ccs_batch`, `bnk_batch`, `jdbc`, `jdbc_banka`, `jpa` |
| `modification_type` | `ControllerOrService`, `ServiceImplOrBiz`, `TypeHandler`, `TwoStep`, `ThreeStep` |
| `llm_provider` | `watsonx_ai`, `watsonx_ai_on_prem`, `claude_ai`, `openai`, `mock` |
| `access_tables` | 암호화 대상 테이블/칼럼 목록 |

See `config.example.json` for complete schema with all options.

### CCS Prefix Configuration

AnyframeCCS 프로젝트에서 `ccs_prefix` 옵션으로 유틸리티 클래스 패턴을 지정합니다:

| Prefix | 암호화 유틸 | 마스킹 유틸 | 용도 |
|--------|-------------|-------------|------|
| `null` | SliEncryptionUtil 직접 호출 | - | 기본값 |
| `"BC"` | BCCommUtil | BCMaskingUtil | BC 프로젝트 |
| `"CP"` | CPCmpgnUtil | CPMaskingUtil | CP 프로젝트 |
| `"CR"` | CRCommonUtil | CRMaskingUtil | CR 프로젝트 |

### Call Graph Traversal

Call Graph (`src/parser/call_graph_builder.py`)는 NetworkX를 사용하여 메서드 호출 관계를 추적합니다:
- 노드: `class_name.method_name` 형태의 메서드
- 엣지: 인수 추적이 포함된 호출 관계
- 순회: DB 접근 지점에서 역방향 BFS로 모든 호출자 식별
- 결과: `Controller → Service → DAO → Mapper` 경로 추적

### Multi-Step Code Generation

복잡한 코드 수정의 정확성을 높이기 위해 **다단계 LLM 협업 전략**을 지원합니다:

#### TwoStep (2단계)
```
Phase 1: Planning (데이터 흐름 분석) → Phase 2: Execution (코드 생성)
```

**설정 예시:**
```json
{
  "modification_type": "TwoStep",
  "two_step_config": {
    "planning_provider": "watsonx_ai",
    "planning_model": "ibm/granite-3-8b-instruct",
    "execution_provider": "watsonx_ai",
    "execution_model": "mistralai/codestral-2505"
  }
}
```

#### ThreeStep (3단계)
```
Phase 1: Query Analysis (VO/SQL 매핑) → Phase 2: Planning (수정 지침) → Phase 3: Execution (코드 생성)
```

Phase 1에서 VO 파일과 SQL 쿼리의 필드 매핑을 먼저 분석하여 Planning의 정확성을 높입니다.

**설정 예시:**
```json
{
  "modification_type": "ThreeStep",
  "three_step_config": {
    "analysis_provider": "watsonx_ai",
    "analysis_model": "ibm/granite-3-8b-instruct",
    "execution_provider": "watsonx_ai",
    "execution_model": "mistralai/codestral-2505"
  }
}
```

#### Execution Modes
두 전략 모두 `execution_options.mode`로 실행 모드를 제어합니다:
- `full`: 전체 파이프라인 실행 (기본값)
- `plan_only`: Planning 단계만 실행, 결과를 `.applycrypto/{two,three}_step_results/`에 저장
- `execution_only`: 이전 Planning 결과를 사용하여 Execution만 실행 (`plan_timestamp` 필요)

### Data Persistence

분석/수정 결과는 대상 프로젝트 내 `.applycrypto/` 디렉토리에 저장됩니다:
- `{target_project}/.applycrypto/results/` — 수정 결과 (JSON)
- `{target_project}/.applycrypto/debug/` — 디버그 로그

`CacheManager`는 파싱 결과를 캐싱하여 후속 실행 속도를 높입니다.

## Important Conventions

### Naming Patterns
| Type | Pattern | Example |
|------|---------|---------|
| Analyzers | `*Analyzer` | `DBAccessAnalyzer` |
| Parsers | `*Parser` | `JavaASTParser` |
| Generators | `*Generator` | `TwoStepCodeGenerator`, `ThreeStepCCSCodeGenerator`, `ThreeStepBankaCodeGenerator` |
| Extractors | `*Extractor` | `MyBatisSQLExtractor` |
| Providers | `*Provider` | `WatsonXAIProvider` |

### Adding New Strategies
새로운 프레임워크나 SQL 타입을 추가할 때:
1. 해당 Strategy 베이스 클래스 상속 (예: `SQLExtractor`, `EndpointExtractionStrategy`)
2. 해당 하위 디렉토리에 구현체 추가
3. Factory 클래스에 enum/생성 로직 추가
4. `config.example.json`에 새 옵션 문서화

### Template System
각 코드 생성기는 Jinja2 템플릿을 사용합니다. 템플릿은 `src/modifier/code_generator/` 하위에 위치합니다.

**디렉토리 구조:**
- `two_step_type/` — TwoStep 전용 (planning, execution)
- `three_step_type/` — ThreeStep 전용 (data_mapping, planning, execution + 보조 vo_extraction)

**Three-step 템플릿 명명 규칙:**
| Phase | 기본 | CCS | CCS Batch | BNK Batch |
|-------|------|-----|-----------|-----------|
| Phase 1 | `data_mapping_template.md` | `*_ccs.md` | `*_ccs_batch.md` | `*_bnk_batch.md` |
| Phase 2 | `planning_template.md` | `*_ccs.md` | `*_ccs_batch.md` | `*_bnk_batch.md` |
| Phase 3 | `execution_template_full.md` / `*_diff.md` | `*_ccs.md` | `*_ccs_batch.md` | `*_bnk_batch.md` |

`*_name_only.md` 접미사: 이름 필드만 처리하는 경량 버전 (CCS, CCS Batch, BNK Batch 각각 존재)

주요 템플릿 변수: `{{source_code}}`, `{{table_info}}`, `{{call_chain}}`, `{{mapping_info}}`

### Error Handling
- 커스텀 예외: `ConfigurationError`, `CodeGeneratorError`, `PersistenceError`
- 로거: `logging.getLogger("applycrypto")`
- 검증: 모든 설정과 데이터 모델에 Pydantic 스키마 사용

## Gotchas

- **테스트 실행 전**: `.env` 파일에 LLM 프로바이더 자격증명이 필요합니다
- **CCS 프로젝트**: `ccs_prefix` 설정 시 `name_only` 모드와 함께 사용해야 할 수 있음
- **캐시 문제**: 분석 결과가 이상할 경우 `python main.py clear`로 캐시 초기화
- **tree-sitter 버전**: Python 3.13에서는 tree-sitter 0.22+ 권장
- **layer_files 키는 소문자**: `db_access_analyzer._find_upper_layer_files()`에서 `classify_layer()` 반환값을 `.lower()`로 변환하여 저장합니다. `"SVCImpl"` → `"svcimpl"`, `"SVC"` → `"svc"`, `"DEM_DAQ"` → `"dem_daq"` 등. Context Generator에서 `layer_files.get("svc", [])`만 호출하면 `"svcimpl"` 키의 파일은 누락되므로 별도 병합이 필요합니다. 단, SQL Extractor가 직접 추가하는 키(`"Repository"`, `"bat"`, `"batvo"`)는 소문자 변환 없이 원본 그대로 저장됩니다.
- **parse_file의 remove_comments 플래그**: `JavaASTParser.parse_file(path, remove_comments=False)`로 호출하면 주석 제거 없이 파싱하여 원본 라인 번호를 보존합니다. `remove_comments=False`일 때는 캐시를 사용하지 않습니다 (키 충돌 방지). ThreeStepBankaCodeGenerator의 BIZ 메서드 추출에서 사용합니다.

## Korean Language Support

이 프로젝트는 한국어를 사용합니다:
- README, 문서화, CLI 메시지
- 도메인 관련 코드 주석

코드 명확성을 위해 변수명과 docstring은 영어로 유지합니다.
