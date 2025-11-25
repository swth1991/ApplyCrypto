# ApplyCrypto: Java Spring Boot 프로젝트 암호화 자동 적용 도구

## Overview

ApplyCrypto는 Java Spring Boot 기반 레거시 시스템에서 민감한 개인정보(주민번호, 이름 등)를 데이터베이스에 암호화하여 저장하도록 소스 코드를 자동으로 분석하고 수정하는 AI 기반 개발 도구입니다. 금융, 보험, 의료 등 개인정보보호가 중요한 산업에서 레거시 코드베이스를 수작업으로 수정하는 데 소요되는 시간과 오류 위험을 획기적으로 줄이고, 규제 준수를 신속하게 달성할 수 있도록 지원합니다.[1][2]

Codestral과 같은 코딩 전문 LLM을 활용하여 프로젝트의 소스 코드를 정적 분석하고, 메서드 호출 흐름을 추적하며, 특정 데이터베이스 테이블 및 칼럼에 접근하는 모든 코드를 식별한 후, 암복호화 로직을 자동으로 삽입합니다. 이를 통해 개발자는 복잡한 레거시 코드의 구조를 파악하는 시간을 절약하고, 비즈니스 로직을 손상시키지 않으면서도 보안 요구사항을 충족할 수 있습니다.[2][3]

## Core Features

### 소스 파일 자동 수집 및 인덱싱

ApplyCrypto는 Java Spring Boot 프로젝트의 모든 소스 파일(.java, .xml 등)을 자동으로 탐색하고 목록화합니다. JSON 형식의 설정 파일을 통해 수집할 파일 타입을 유연하게 지정할 수 있으며, 수집된 파일 정보는 구조화된 메타데이터로 저장되어 이후 분석 단계에서 신속하게 활용됩니다. 이 기능은 대규모 레거시 프로젝트에서 분석 대상을 명확히 정의하는 기초를 제공하며, 중복 분석을 방지하고 프로젝트 구조를 한눈에 파악할 수 있도록 합니다.[4][1]

### Call Graph 생성 및 메서드 추적

각 REST API 엔드포인트를 시작점으로 하여 Controller → Service → DAO → Mapper 레이어를 거쳐 데이터베이스 접근까지 이어지는 메서드 호출 체인(call graph)을 자동으로 생성합니다. Python 기반 Java AST 파서(javalang, jAST 등)를 활용하여 각 메서드의 이름, 반환 타입, 입력 파라미터를 상세히 추출하고, caller-callee 관계를 트리 구조로 시각화합니다. 이를 통해 복잡한 레이어 간 의존성을 명확히 이해하고, 특정 테이블 접근 경로를 역추적하여 수정 대상 파일을 정확히 식별할 수 있습니다.[5][4]

### DB 테이블 접근 코드 자동 식별

사용자가 JSON 설정 파일에 지정한 데이터베이스 테이블 및 칼럼 정보를 기반으로, 해당 테이블에 접근하는 모든 소스 코드를 자동으로 필터링합니다. MyBatis의 Mapper XML 파일이나 JDBC 기반 SQL 실행 코드를 정규표현식 및 XML 파서로 분석하여 쿼리 내 테이블명과 칼럼명을 추출하고, 이와 연결된 DTO/VO, DAO, Service, Controller 파일을 순차적으로 매핑합니다. SQL Wrapping 방식(MyBatis, JDBC 등)에 따라 코드 구조가 달라지므로, 설정 파일의 sql_wrapping_type 정보를 참조하여 적응적으로 파일을 탐색합니다.[1][4]

### 암복호화 코드 자동 삽입

식별된 소스 파일에 k-sign.CryptoService 클래스의 encrypt/decrypt 메서드 호출을 자동으로 삽입하여, 지정된 칼럼 데이터가 암호화된 상태로 데이터베이스에 저장되고 읽을 때 복호화되도록 수정합니다. DTO/VO의 getter/setter 메서드를 우선 수정하고, Call Graph를 참조하여 상위 레이어(DAO, Service, Controller)까지 연쇄적으로 수정 작업을 확장합니다. 비즈니스 로직은 절대 변경하지 않으며, 수정된 코드에는 한글 주석을 추가하여 암복호화 적용 이유와 위치를 명확히 표시합니다. 수정 완료 후에는 테이블별, 칼럼별 수정 파일 목록을 JSON 형태로 저장하여 추적 가능성을 보장합니다.[2][4][5][1]

## CLI 기반 사용자 인터페이스

ApplyCrypto는 명령줄 인터페이스(CLI)를 통해 모든 기능을 제공하며, 직관적이고 스크립트 자동화가 용이한 명령어 체계를 갖추고 있습니다. `analyze` 명령으로 프로젝트를 분석하고, `list` 명령으로 소스 파일, DB 접근 파일, 수정된 파일, 엔드포인트 목록을 조회하며, `modify` 명령으로 암복호화 코드를 일괄 적용합니다. 각 명령은 직관적인 옵션(–all, –db, –modified, –endpoint, –callgraph)을 지원하여 개발자가 원하는 정보를 신속히 확인할 수 있습니다.[4][1]

## User Experience

### 사용자 페르소나

**레거시 시스템 유지보수 개발자**: 10년 이상 운영된 Java Spring Boot 기반 금융권 시스템을 담당하며, 개인정보보호법 강화에 따라 주민번호 등 민감 정보를 암호화해야 하는 긴급 요구사항을 받은 개발자입니다. 수백 개의 소스 파일과 복잡한 레이어 구조를 수작업으로 분석하고 수정하는 것은 시간이 오래 걸리고 오류 위험이 높아, 자동화 도구를 통해 신속하고 정확하게 작업을 완료하고자 합니다.[1][2]

**보안 컴플라이언스 담당자**: 조직의 보안 정책 준수를 책임지며, 개발팀이 암호화 요구사항을 정확히 적용했는지 검증하고 추적해야 하는 역할입니다. ApplyCrypto가 생성하는 수정 파일 목록과 Call Graph를 통해 어떤 테이블과 칼럼이 어떤 코드에서 처리되는지 명확히 파악하고, 감사 자료로 활용할 수 있습니다.[2][1]

### 주요 사용 흐름

**프로젝트 초기 분석**: 개발자는 ApplyCrypto 설정 파일에 프로젝트 경로, 분석 대상 파일 확장자, SQL Wrapping 타입을 지정한 후 `analyze` 명령을 실행합니다. 도구는 프로젝트를 스캔하여 소스 파일을 수집하고, AST 파싱 및 Call Graph를 생성하며, 결과를 JSON 파일로 저장합니다. 이미 분석된 프로젝트라면 재분석 여부를 사용자에게 확인하여 불필요한 중복 작업을 방지합니다.[4][1]

**DB 접근 코드 식별**: 개발자는 설정 파일에 암호화 대상 테이블(예: EMPLOYEE, CUSTOMER)과 칼럼(예: JUMIN_NUMBER, NAME)을 JSON 형태로 기술합니다. `list --db` 명령을 실행하면 해당 테이블에 접근하는 Mapper XML, DAO, DTO, Service, Controller 파일 목록이 테이블별로 정리되어 출력되며, 개발자는 수정 범위를 사전에 확인할 수 있습니다.[1][4]

**암복호화 코드 적용**: `modify` 명령을 실행하면 ApplyCrypto는 식별된 파일에 대해 하위 레이어(DTO getter/setter)부터 상위 레이어(Controller)까지 순차적으로 암복호화 로직을 삽입합니다. 수정된 코드는 원본과 함께 버전 관리되며, `list --modified` 명령으로 수정 내역을 테이블별로 확인할 수 있습니다. 개발자는 수정된 파일을 검토하고 테스트 후 배포합니다.[2][1]

**Call Graph 시각화**: 특정 엔드포인트에서 어떤 메서드들이 호출되는지 확인하고 싶을 때, `list --callgraph <endpoint>` 명령으로 트리 형태의 호출 그래프를 출력하여 코드 흐름을 한눈에 파악할 수 있습니다. 이는 디버깅과 코드 리뷰 시 유용하게 활용됩니다.[5][4]

### UI/UX 고려사항

CLI 명령어는 직관적이고 일관된 네이밍(analyze, list, modify)을 사용하여 학습 곡선을 낮추고, 각 명령은 명확한 피드백 메시지와 진행 상황 표시를 제공합니다. 설정 파일은 JSON 형식으로 구조화되어 가독성과 편집 용이성을 보장하며, 오류 발생 시 상세한 에러 메시지와 로그를 출력하여 문제 해결을 돕습니다. 출력 결과는 테이블 형태 또는 계층 구조로 정리되어 대량의 정보를 효율적으로 전달합니다.[5][4][1]

## Technical Architecture

### 설계 고려 사항

- 작성 언어는 Python 3.13으로 하며 필요한 package를 import해서 사용하도록 한다. 오픈 소스 package의 경우 손쉽게 구현할 수 있는 것들은 직접 구현하고, 복잡하고 시간이 많이 걸리는 것들은 오픈 소스를 사용하도록 한다. 오픈 소스를 사용하는 경우에도 해당 pakcage가 active하게 유지보수 되고 있다는 점을 확신해야 한다.[4]

- OOP 프로그래밍과 Python 언어의 특성을 고려하여 대표적인 디자인 패턴을 적극 사용함으로써 확장성, 유지 보수, 디커플링, 쉬운 가독성, 성능 등을 달성하도록 한다. 특히 다음과 같은 SOLID 설계 원칙을 적극적으로 적용하도록 한다:[4]
  - **단일 책임 원칙 (Single Responsibility Principle, SRP)**: 클래스는 단 하나의 책임만을 가져야한다. 클래스 변경의 이유는 오직 하나만 존재해야 한다.[4]
  - **개방-폐쇄 원칙 (Open-Closed Principle, OCP)**: 확장에는 열려있어야 하고 수정에는 닫혀있어야 한다. 기존 코드를 변경하지 않고 새로운 기능을 추가할 수 있어야 한다.[4]
  - **리스코프 치환 원칙 (Liskov Substitution Principle, LSP)**: 자식 클래스는 부모 클래스와 교체 가능해야 한다. 자식 클래스는 부모 클래스의 계약을 준수해야 한다.[4]
  - **인터페이스 분리 원칙 (Interface Segregation Principle, ISP)**: 클라이언트는 사용하지 않는 메서드에 의존해서는 안된다. 큰 인터페이스는 작게 나누고 필요한 메서드만 제공해야 한다.[4]
  - **의존성 역전 원칙 (Dependency Inversion Principle, DIP)**: 상위 수준의 모듈은 하위 수준의 모듈에 의존해서는 안된다. 추상화에 의존하고 구체적인 구현에는 의존하지 않아야 한다.[4]

- 그리고 추가로 아래와 같은 설계 원칙도 고려한다:[4]
  - **DRY(Don't repeat yourself)**: 공통적인 처리는 공통함수나 클래스로 정의해서 사용한다.[4]

### 시스템 컴포넌트

**Configuration Manager**: JSON 설정 파일을 로드하고 검증하는 모듈로, source_file_types, access_tables, sql_wrapping_type 등의 설정값을 파싱하여 다른 컴포넌트에 제공합니다. 설정 파일 스키마 검증을 통해 사용자 입력 오류를 사전에 방지합니다.[1][4]

**Source File Collector**: 프로젝트 디렉터리를 재귀적으로 탐색하여 설정에 지정된 확장자(.java, .xml)의 파일을 수집하고, 파일 경로와 메타데이터를 JSON 구조로 저장하는 모듈입니다. Python의 pathlib과 os 모듈을 활용하여 크로스 플랫폼 호환성을 보장합니다.[4]

**Java AST Parser**: javalang 또는 jAST 라이브러리를 사용하여 Java 소스 코드를 추상 구문 트리(AST)로 파싱하고, 클래스, 메서드, 변수 정보를 추출하는 모듈입니다. ANTLR 기반 파서를 통해 최신 Java 버전을 지원하며, 메서드 시그니처(이름, 반환 타입, 파라미터)를 상세히 분석합니다.[5][4]

**XML Mapper Parser**: lxml 또는 xml.etree.ElementTree를 사용하여 MyBatis Mapper XML 파일을 파싱하고, `<select>`, `<insert>`, `<update>`, `<delete>` 태그 내 SQL 쿼리에서 테이블명과 칼럼명을 정규표현식으로 추출하는 모듈입니다. CDATA 섹션 처리 및 MyBatis 파라미터 표기법(#{})을 정확히 해석합니다.[4]

**Call Graph Builder**: AST 정보를 기반으로 메서드 호출 관계(caller-callee)를 추적하여 그래프 구조를 생성하고, 엔드포인트부터 DAO/Mapper까지 이어지는 트리를 구성하는 모듈입니다. networkx 라이브러리를 활용하여 그래프 탐색 및 시각화를 효율적으로 수행합니다.[5][4]

**DB Access Analyzer**: 설정 파일의 테이블 및 칼럼 정보와 XML/Java 파일에서 추출한 SQL 쿼리를 비교하여, 특정 테이블에 접근하는 파일을 필터링하고 태그를 부여하는 모듈입니다. SQL Wrapping Type에 따라 탐색 전략을 동적으로 변경합니다(Strategy Pattern).[4]

**Code Modifier**: 식별된 소스 파일의 AST를 수정하여 암복호화 로직을 삽입하고, 수정된 AST를 Java 소스 코드로 다시 변환(unparsing)하는 모듈입니다. CryptoService의 encrypt/decrypt 메서드 호출을 getter/setter에 삽입하고, import 문을 자동으로 추가하며, 한글 주석을 삽입합니다.[5]

**CLI Controller**: argparse를 사용하여 CLI 명령어와 옵션을 파싱하고, 각 명령에 해당하는 비즈니스 로직 모듈을 호출하는 진입점 역할을 합니다. 명령어 실행 결과를 포맷팅하여 콘솔에 출력하고, 로그와 에러 메시지를 관리합니다.[1][4]

**Data Persistence Layer**: 분석 결과(소스 파일 목록, Call Graph, DB 접근 파일 목록, 수정 내역)를 JSON 파일로 직렬화하여 저장하고 로드하는 모듈입니다. 데이터 구조는 JSON Schema로 정의되어 일관성을 유지합니다.[1][4]

### 데이터 모델

**SourceFile**: 파일 경로, 파일명, 확장자, 관련 테이블 태그 목록을 포함하는 모델입니다. 예시: `{"path": "/src/main/java/com/example/dto/EmployeeDTO.java", "tags": ["EMPLOYEE"]}`.[1][4]

**Method**: 메서드 이름, 반환 타입, 파라미터 목록, 소속 클래스, 파일 경로를 포함하는 모델입니다. 예시: `{"name": "getEmployee", "return_type": "EmployeeDTO", "params": [{"name": "id", "type": "Long"}]}`.[1][4]

**CallRelation**: caller 메서드와 callee 메서드를 연결하는 관계 모델로, Call Graph의 엣지를 구성합니다. 예시: `{"caller": "EmployeeController.getEmployee", "callee": "EmployeeService.findById"}`.[5][1]

**TableAccessInfo**: 테이블 이름, 칼럼 목록, 접근하는 파일 목록, SQL 쿼리 타입(SELECT/INSERT/UPDATE/DELETE)을 포함하는 모델입니다. 예시: `{"table": "EMPLOYEE", "columns": ["JUMIN_NUMBER"], "files": ["EmployeeMapper.xml", "EmployeeDTO.java"]}`.[1][4]

**ModificationRecord**: 수정된 파일 경로, 테이블명, 칼럼명, 수정 일시, 수정 전후 코드 diff를 포함하는 모델입니다. 예시: `{"file": "EmployeeDTO.java", "table": "EMPLOYEE", "column": "JUMIN_NUMBER", "timestamp": "2025-11-23T17:00:00"}`.[1]

### API 및 통합

ApplyCrypto는 외부 API와의 통합보다는 내부 모듈 간 인터페이스 설계에 중점을 둡니다. 각 컴포넌트는 추상 인터페이스(ABC)를 통해 디커플링되며, 의존성 주입(Dependency Injection) 패턴을 적용하여 테스트와 확장을 용이하게 합니다. Codestral 등 LLM API를 호출하는 경우, LLMClient 추상 클래스를 정의하고 구체적인 API(OpenAI, HuggingFace 등)는 구현 클래스로 분리합니다.[3][4]

#### 기본적으로 지원해야 하는 LLM 플래폼은 다음과 같습니다. - watsonx.ai, OpenAI, Claude.ai

### 인프라 요구사항

**개발 환경**: Python 3.13 이상, pip 패키지 관리자, 가상환경(venv) 사용을 권장합니다. 필수 Python 패키지: javalang 또는 jAST(Java AST 파싱), lxml(XML 파싱), networkx(그래프 처리), argparse(CLI), pytest(테스트).[5][4]

**실행 환경**: Linux, macOS, Windows 모두 지원하며, Java Spring Boot 프로젝트 소스 코드에 대한 읽기 권한이 필요합니다. 대규모 프로젝트 분석 시 최소 4GB RAM, 멀티코어 CPU를 권장합니다.[4]

**저장소**: 분석 결과와 수정 내역을 저장할 로컬 파일 시스템 공간(프로젝트당 약 10~100MB)이 필요합니다. 향후 확장 시 SQLite 또는 PostgreSQL 데이터베이스를 지원할 수 있습니다.[1][4]

**LLM 통합**: Codestral API 호출을 위한 네트워크 연결과 API 키가 필요하며, 로컬 LLM 사용 시 vLLM 또는 Ollama 서버가 필요합니다.[3]

## Development Roadmap

### MVP (Minimum Viable Product)

#### Phase 1: 기본 분석 및 수집 기능

- Configuration Manager 구현: JSON 설정 파일 로드 및 검증 기능[1][4]
- Source File Collector 구현: .java, .xml 파일 재귀 탐색 및 목록화[4]
- CLI 기본 구조 구현: analyze, list –all 명령어 지원[1]
- 데이터 영속화: 소스 파일 목록을 JSON으로 저장/로드[1]

#### Phase 2: Java 코드 파싱 및 Call Graph 생성

- Java AST Parser 구현: javalang 또는 jAST를 사용한 클래스/메서드 추출[5]
- Call Graph Builder 구현: 메서드 호출 관계 추적 및 트리 구조 생성[5]
- list –endpoint, list –callgraph 명령어 구현[1]

#### Phase 3: DB 접근 코드 식별

- XML Mapper Parser 구현: MyBatis XML에서 SQL 쿼리 및 테이블명 추출[4]
- DB Access Analyzer 구현: 테이블/칼럼 기반 파일 필터링 및 태그 부여[4]
- list –db 명령어 구현[1]

#### Phase 4: 코드 자동 수정 및 암복호화 적용

- Code Modifier 구현: AST 수정 및 CryptoService 호출 삽입[5]
- 하위 레이어(DTO/VO)부터 상위 레이어(Controller)까지 순차 수정[2]
- modify 명령어 및 list –modified 명령어 구현[1]

### Future Enhancements

#### Phase 5: JDBC 및 다양한 SQL Wrapping 지원

- JDBC PreparedStatement 기반 SQL 파싱 및 수정 로직 추가[4]
- JPA Entity 어노테이션 기반 암복호화 적용 지원[4]
- sql_wrapping_type별 Strategy Pattern 확장[4]

#### Phase 6: LLM 통합 및 지능형 코드 분석

- Codestral API 통합: 복잡한 비즈니스 로직 분석 및 수정 제안[3]
- LLMClient 추상화 및 다중 LLM 지원(OpenAI, HuggingFace)[3]
- 코드 수정 전 영향 분석 및 리스크 평가 기능[2]

#### Phase 7: 고급 분석 및 리포팅

- 수정 전후 코드 diff 시각화 및 HTML 리포트 생성[5][1]
- Call Graph 대화형 시각화(웹 기반 인터페이스)[5]
- 암호화 적용률 통계 및 컴플라이언스 리포트[2]

#### Phase 8: 성능 최적화 및 대규모 프로젝트 지원

- 병렬 처리를 통한 분석 속도 향상(multiprocessing)[4]
- 증분 분석(incremental analysis) 지원: 변경된 파일만 재분석[4]
- 데이터베이스 백엔드 지원(SQLite, PostgreSQL)[4]

#### Phase 9: 확장 가능한 플러그인 시스템

- 사용자 정의 파서 및 수정 로직 플러그인 인터페이스[4]
- 다양한 암호화 라이브러리 지원(AES, RSA, 커스텀)[2]
- 다국어 주석 및 로그 메시지 지원[4]

### 코딩 시 고려할 사항

- 코드 작성 시 복잡하고 긴 코드를 한 번에 작성하지 않고 작은 단위 함수로 쪼개고 모듈화를 진행한다. 다소 긴 함수 작성이 불가피 할 때는 함수 내에서 5~10줄 정도의 단위로 코드 블락을 나누어서 작성한다.[4]

- 중첩된 코드의 작성을 최대한 회피하고 불가피한 경우라 할지라도 중첩 depth가 너무 깊어지지 않도록 최대한 노력한다.[4]

- 클래스, 함수, 변수 이름에는 구체적이고 설명적인 이름을 사용한다.[4]

- 작성된 소스 코드에 대한 키워드 검색이 효과적으로 동작할 수 있도록 통일되고 일관된 명명 규칙을 적용한다.[4]

- 입출력 변수에 대해서는 어노테이션 또는 타입힌트를 사용하여 그 의미를 명확히 한다.[4]

- Class, Property, Method, code logic에 한글로된 주석을 간결하고 명확하게 삽입하여 코드를 이해하기 쉽게 만든다.[5]

- 복잡한 정규 표현식, 수식, 알고리즘에는 반드시 주석을 달아서 이해하기 쉽도록 한다.[5]

- 그외 코딩 규칙은 "PEP 8"의 가이드를 따르도록 한다.[4]

- LLM 추론을 위해 사용할 프롬프트는 별개의 텍스트 파일로 분리해서 템플릿으로 저장하고 이를 읽어들여 필요한 내용을 삽입 후 (예를 들면 few shot 예제) 사용하는 방안을 적용한다.

## Logical Dependency Chain

### 개발 순서 및 의존성

**Foundation (Phase 1)**: 모든 기능의 기반이 되는 설정 관리 및 파일 수집 기능을 우선 구현하여, 프로젝트 구조를 파악하고 이후 분석 작업의 입력 데이터를 확보합니다. CLI 기본 구조도 이 단계에서 구축하여 사용자 피드백을 조기에 받을 수 있습니다.[1][4]

**Visibility (Phase 2)**: Java 코드를 파싱하고 Call Graph를 생성하여 프로젝트의 메서드 호출 흐름을 시각화합니다. 이 단계에서 사용자는 엔드포인트 목록과 Call Graph를 CLI로 확인할 수 있어, 도구의 분석 능력을 직접 체험할 수 있습니다.[5][1]

**Core Value (Phase 3-4)**: DB 접근 코드를 식별하고 암복호화 로직을 자동 삽입하는 핵심 기능을 구현합니다. Phase 3에서 수정 대상을 정확히 특정하고, Phase 4에서 실제 코드 수정을 수행하여 MVP의 완성도를 확보합니다.[2][1]

**Expansion (Phase 5-6)**: MyBatis 외 JDBC, JPA 등 다양한 SQL Wrapping 방식을 지원하고, LLM을 통합하여 지능형 분석 기능을 추가합니다. 이 단계부터는 사용자 피드백을 반영한 기능 확장이 이루어집니다.[3][1][4]

**Optimization (Phase 7-9)**: 성능 최적화, 고급 리포팅, 플러그인 시스템 등 사용성과 확장성을 높이는 기능을 단계적으로 추가합니다. 각 Phase는 이전 Phase의 안정성을 전제로 하며, 독립적으로 테스트 가능한 단위로 설계됩니다.[4]

### Atomic Feature Scoping

각 Phase는 독립적으로 배포 및 테스트 가능한 기능 단위로 구성되며, Phase 1 완료 시점에 기본 파일 수집 및 출력이 가능하고, Phase 2 완료 시점에 Call Graph 조회가 가능합니다. Phase 4까지 완료되면 전체 워크플로우가 동작하는 MVP가 완성되며, 이후 Phase는 기존 기능을 손상시키지 않고 점진적으로 개선하는 방식으로 진행됩니다.[2][1][4]

## Risks and Mitigations

### 기술적 도전

**Java 코드 파싱의 정확성**: javalang은 Java 8까지 지원하며 최신 Java 버전(11, 17)의 문법을 완전히 파싱하지 못할 수 있습니다. 이를 완화하기 위해 jAST(ANTLR 기반)를 우선 사용하고, 파싱 실패 시 대체 파서로 fallback하는 전략을 적용합니다. 또한 정규표현식을 보조 수단으로 활용하여 핵심 정보(메서드명, 클래스명)를 추출합니다.[4]

**복잡한 레이어 간 의존성 추적**: 동적 프록시, 리플렉션, 람다 표현식 등으로 인해 정적 분석만으로는 Call Graph를 완벽히 구성하기 어렵습니다. 이를 완화하기 위해 Spring Framework의 어노테이션(@Controller, @Service, @Autowired)을 참조하여 의존성을 추론하고, LLM을 활용해 불확실한 호출 관계를 분석합니다.[3][4]

**코드 수정 시 비즈니스 로직 손상 위험**: AST 수정 과정에서 의도치 않게 비즈니스 로직이 변경되거나 구문 오류가 발생할 수 있습니다. 이를 완화하기 위해 수정 전 백업을 자동 생성하고, 수정된 코드를 Java 컴파일러로 검증하며, 단위 테스트를 자동 실행하여 회귀 오류를 조기 발견합니다. 또한 수정 범위를 getter/setter로 제한하여 영향 범위를 최소화합니다.[2][4]

### MVP 정의 및 범위 조정

ApplyCrypto의 MVP는 MyBatis 기반 Java Spring Boot 프로젝트에서 지정된 DB 테이블/칼럼에 접근하는 코드를 식별하고, DTO의 getter/setter에 암복호화 로직을 삽입하는 것으로 정의합니다. JDBC, JPA, 복잡한 비즈니스 로직 수정은 MVP 범위에서 제외하고 이후 Phase로 미루어, 초기 개발 리스크를 낮추고 빠른 사용자 검증을 가능하게 합니다.[2][1]

### 리소스 제약

**개발 인력 및 시간**: 제한된 인력으로 모든 기능을 한 번에 구현하기 어려우므로, Phase별 우선순위를 명확히 하고 핵심 기능(Phase 1-4)에 집중합니다. SOLID 원칙과 모듈화를 철저히 적용하여 향후 기능 추가 시 기존 코드 수정을 최소화합니다.[1][4]

**오픈소스 라이브러리 유지보수 중단**: javalang은 2016년 이후 업데이트가 중단되었으며, 최신 Java 문법을 지원하지 않습니다. 이를 완화하기 위해 jAST(2025년 활발히 개발 중)를 주요 파서로 채택하고, 라이브러리 선택 시 GitHub Star 수, 최근 커밋 이력, 커뮤니티 활성도를 평가합니다. 필요 시 자체 파서 모듈을 개발할 수 있도록 추상화 계층을 설계합니다.[4]

**대규모 프로젝트 성능**: 수천 개의 파일을 분석할 때 메모리 부족 및 처리 시간 증가 문제가 발생할 수 있습니다. 이를 완화하기 위해 파일 단위 병렬 처리(multiprocessing)를 적용하고, 분석 결과를 캐싱하며, 증분 분석을 지원하여 변경된 파일만 재분석합니다.[4]

## Appendix

### 연구 조사 결과

**Java 정적 분석 도구 현황**: SonarQube, SpotBugs, Checkstyle 등은 코드 품질 및 버그 탐지에 강점이 있으나, 커스텀 코드 수정 기능은 제공하지 않습니다. java-callgraph는 정적 Call Graph 생성을 지원하지만 Python 통합이 어렵습니다. jAST는 Python에서 Java AST를 생성하고 수정할 수 있는 최신 도구로, ApplyCrypto의 핵심 라이브러리로 적합합니다.[5][4]

**MyBatis 매핑 메커니즘**: MyBatis는 Mapper 인터페이스의 메서드와 XML 파일의 SQL 문을 namespace와 id로 매핑하며, 파라미터는 @Param 어노테이션과 #{} 표기법으로 전달됩니다. XML의 `<select>`, `<insert>`, `<update>`, `<delete>` 태그 내 SQL 쿼리는 CDATA 섹션에 포함되며, 테이블명과 칼럼명은 정규표현식으로 추출 가능합니다.[4]

**Python AST 파싱 라이브러리 비교**: javalang은 가볍고 사용이 간단하지만 Java 8까지만 지원하며 업데이트가 중단되었습니다. jAST는 ANTLR 기반으로 최신 Java 버전을 지원하고 AST 수정 및 unparsing을 제공하여 ApplyCrypto의 요구사항에 가장 적합합니다. ANTLR Python 런타임을 직접 사용하는 방안도 있으나 학습 곡선과 개발 시간이 증가합니다.[5][4]

### 기술 사양

#### 설정 파일 JSON 스키마

```json
{
  "project_path": "/path/to/project",
  "source_file_types": [".java", ".xml"],
  "sql_wrapping_type": "mybatis",
  "access_tables": [
    {
      "table_name": "EMPLOYEE",
      "columns": ["NAME", "JUMIN_NUMBER"]
    }
  ]
}
```

#### Call Graph JSON 구조

```json
{
  "endpoints": [
    {
      "url": "/api/employee/{id}",
      "method": "GET",
      "controller": "EmployeeController.getEmployee",
      "call_chain": [
        {"caller": "EmployeeController.getEmployee", "callee": "EmployeeService.findById"},
        {"caller": "EmployeeService.findById", "callee": "EmployeeMapper.selectById"}
      ]
    }
  ]
}
```

#### 코드 수정 예시

EmployeeDTO의 getter/setter에 CryptoService 호출 삽입

```java
// 수정 전
public String getJuminNumber() {
    return juminNumber;
}

// 수정 후
import k-sign.CryptoService;
public String getJuminNumber() {
    return CryptoService.decrypt(juminNumber); // ApplyCrypto: 암호화 적용
}
```

---

[1](https://dataprodmgmt.substack.com/p/how-i-use-chatgpt-to-generate-markdown)
[2](https://productschool.com/blog/product-strategy/product-template-requirements-document-prd)
[3](https://reeganalward.com/master-the-blueprint-llm-prompts-for-perfect-product-requirements-documents-prd-192b23835462)
[4](https://community.ibm.com/community/user/blogs/hiren-dave/2025/05/27/markdown-documentation-best-practices-for-document)
[5](https://dev.to/auden/10-markdown-tips-for-creating-beautiful-product-documentation-in-2025-5ek4)
[6](https://www.notion.com/templates/category/product-requirements-doc)
[7](https://brunch.co.kr/@yongjinjinipln/221)
[8](https://help.obsidian.md/syntax)
[9](https://nonstop-antoine.tistory.com/144)
[10](https://www.markdownguide.org/basic-syntax/)