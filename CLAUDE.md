# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ApplyCrypto is an AI-powered tool that automatically analyzes and modifies Java Spring Boot legacy systems to encrypt/decrypt sensitive personal information in database operations. It uses static code analysis, call graph traversal, and LLM-based code generation to insert encryption logic into identified files.

## Common Commands

### Setup and Installation
```bash
# Windows PowerShell setup
./scripts/setup.ps1

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.\.venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Tool
```bash
# Analyze project (collect source files, build call graph, identify DB access patterns)
python main.py analyze --config config.json

# List analysis results
python main.py list --all          # All source files
python main.py list --db           # Table access information
python main.py list --endpoint     # REST API endpoints
python main.py list --callgraph EmpController.login  # Method call chain
python main.py list --modified     # Modified files history

# Modify code (insert encryption/decryption logic)
python main.py modify --config config.json --dry-run  # Preview only
python main.py modify --config config.json            # Apply changes

# Launch Streamlit UI
python run_ui.py
```

### Development Commands
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Linting (Windows)
./scripts/lint.ps1

# Linting (manual)
isort .
ruff format
ruff check --fix
```

### Environment Variables
Create a `.env` file with LLM provider credentials:
```
WATSONX_API_URL=https://us-south.ml.cloud.ibm.com
WATSONX_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
```

## Architecture Overview

### Layered Architecture Flow
The system follows a strict layered architecture with clear separation of concerns:

1. **CLI Layer** (`src/cli/`) → Entry point that orchestrates all other layers
2. **Configuration Layer** (`src/config/`) → Loads and validates JSON config with Pydantic schemas
3. **Collection Layer** (`src/collector/`) → Recursively collects source files with filtering
4. **Parsing Layer** (`src/parser/`) → Parses Java AST and XML Mappers, builds call graphs
5. **Analysis Layer** (`src/analyzer/`) → Identifies DB access patterns via call graph traversal
6. **Modification Layer** (`src/modifier/`) → LLM-based code generation and patching
7. **LLM Layer** (`src/modifier/llm/`) → Abstract provider interface with multiple implementations
8. **Persistence Layer** (`src/persistence/`) → JSON serialization and caching

### Key Design Patterns

**Strategy Pattern** is used extensively:
- `LLMProvider`: WatsonX, OpenAI, Claude implementations
- `EndpointExtractionStrategy`: Framework-specific endpoint extraction (SpringMVC, AnyframeSarangOn)
- `SQLExtractor`: SQL wrapping type strategies (MyBatis, JDBC, JPA, Anyframe JDBC)
- `BaseCodeGenerator`: Modification type strategies (TypeHandler, ControllerOrService, ServiceImplOrBiz)
- `ContextGenerator`: Context generation strategies (MyBatis, JDBC, PerLayer)

**Factory Pattern**:
- `LLMFactory`: Creates appropriate LLM provider based on config
- `EndpointExtractionStrategyFactory`: Creates framework-specific endpoint extractors
- `SQLExtractorFactory`: Creates SQL extractor based on wrapping type
- `CodeGeneratorFactory`: Creates code generator based on modification type
- `ContextGeneratorFactory`: Creates context generator based on SQL wrapping type

### Configuration Schema

The `config.json` file drives the entire workflow. Critical fields:

- `framework_type`: Framework detection strategy (`SpringMVC`, `AnyframeSarangOn`, etc.)
- `sql_wrapping_type`: How SQL is accessed (`mybatis`, `jdbc`, `jpa`)
- `modification_type`: Where to insert encryption logic (`TypeHandler`, `ControllerOrService`, `ServiceImplOrBiz`)
- `llm_provider`: AI model to use (`watsonx_ai`, `claude_ai`, `openai`, `mock`)
- `access_tables`: Tables/columns requiring encryption
- `generate_full_source`: Whether to include full source in prompts (uses `template_full.md` instead of `template.md`)

See `config.example.json` for complete schema.

### Call Graph Traversal

The call graph (`src/parser/call_graph_builder.py`) uses NetworkX to build a directed graph of method calls:
- Nodes: Methods (identified by `class_name.method_name`)
- Edges: Call relationships with argument tracking
- Entry points: REST endpoints extracted via framework-specific strategies
- Traversal: Reverse BFS from DB access points to find all callers

This enables tracing: `Controller → Service → DAO → Mapper` to identify which files need encryption logic.

### LLM-Based Code Modification

The modification workflow (`src/modifier/code_modifier.py`):

1. **Context Generation**: `ContextGenerator` creates `ModificationContext` objects with:
   - Source file content (full or partial based on `generate_full_source`)
   - Table/column metadata
   - Framework-specific hints

2. **Prompt Template Rendering**: Jinja2 templates (`template.md` or `template_full.md`) in each code generator directory are rendered with context variables

3. **LLM Code Generation**: `BaseCodeGenerator` subclasses call LLM provider and parse response

4. **Code Patching**: `CodePatcher` applies unified diff format patches to source files

5. **Error Handling**: `ErrorHandler` provides automatic retry with exponential backoff

6. **Result Tracking**: `ResultTracker` records all modifications with metadata

### Parsing Infrastructure

**Java AST Parsing** (`src/parser/java_ast_parser.py`):
- Uses `tree-sitter` with `tree-sitter-java` grammar
- Extracts: classes, methods, annotations, method calls
- Captures method signatures with parameters and return types

**MyBatis XML Parsing** (`src/parser/xml_mapper_parser.py`):
- Uses `lxml` to parse SQL mapper XMLs
- Extracts SQL queries from `<select>`, `<insert>`, `<update>`, `<delete>` tags
- Identifies table/column references from SQL text

**Call Graph Building** (`src/parser/call_graph_builder.py`):
- Combines parsed Java and XML data
- Builds directed graph with method calls as edges
- Stores method metadata (class, package, file path, line numbers)
- Supports argument tracking for method invocations

### SQL Extraction Strategies

Different projects wrap SQL in different ways. `SQLExtractor` implementations handle:

- **MyBatis**: Extract from XML mapper files, match to Java DAO methods
- **JDBC**: Find `PreparedStatement` and SQL strings in Java code
- **JPA**: Parse entity annotations and JPQL queries
- **Anyframe JDBC**: Handle StringBuilder-based dynamic SQL construction
- **LLM Fallback**: When static analysis fails, use LLM to extract SQL from code

### Data Persistence

All intermediate results are persisted as JSON:
- Source files metadata: `{project_root}/build/applycrypto_source_files.json`
- Call graph: `{project_root}/build/applycrypto_call_graph.json`
- Table access info: `{project_root}/build/applycrypto_table_access.json`
- Modification records: `{project_root}/build/applycrypto_modification_records.json`

Custom JSON encoder/decoder (`src/persistence/`) handle dataclass serialization.

Caching (`src/persistence/cache_manager.py`) stores parsed results to speed up subsequent runs.

## Important Conventions

### Module Organization
- Each layer is a top-level package under `src/`
- Strategy implementations go in subdirectories (e.g., `sql_extractors/`, `endpoint_strategy/`, `code_generator/`)
- Factory classes create strategies based on config enums
- Base classes are abstract with clear interfaces

### Naming Patterns
- Analyzers: `*Analyzer` (e.g., `DBAccessAnalyzer`)
- Parsers: `*Parser` (e.g., `JavaASTParser`, `XMLMapperParser`)
- Builders: `*Builder` (e.g., `CallGraphBuilder`)
- Generators: `*Generator` (e.g., `TypeHandlerCodeGenerator`)
- Extractors: `*Extractor` (e.g., `MyBatisSQLExtractor`)
- Providers: `*Provider` (e.g., `WatsonXAIProvider`)
- Strategies: `*Strategy` (e.g., `EndpointExtractionStrategy`)

### Error Handling
- Custom exception classes: `ConfigurationError`, `CodeGeneratorError`, `PersistenceError`
- Logger naming: Use module path (e.g., `logging.getLogger(__name__)`)
- Validation: Pydantic schemas for all config and data models

### Template System
- Each code generator type has its own directory with templates
- `template.md`: Partial source context (default)
- `template_full.md`: Full source context (when `generate_full_source: true`)
- Templates use Jinja2 syntax with variables like `{{source_code}}`, `{{table_info}}`

## Testing Guidelines

- Test files mirror source structure: `test_{module_name}.py`
- Integration tests: `test_integration_*.py`
- Use pytest fixtures for common setup
- Mock LLM providers with `MockLLMProvider` for testing modification logic
- Test data in `tests/` directory or inline as strings

## Korean Language Support

This project uses Korean (한글) for:
- README and documentation
- CLI help messages and logging
- Comments in Korean for domain-specific context
- Variable names and docstrings in English for code clarity

When modifying Korean text, ensure UTF-8 encoding is preserved.
