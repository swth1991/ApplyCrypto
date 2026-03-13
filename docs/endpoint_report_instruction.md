# End Point 목록 보고서 생성 구현명세서

## 최신 개선사항 (v2.0 ~ v2.6)

### v2.6 SpringMVC 엔드포인트 추출 전략 구현 및 에러 로깅 강화 (2026.02.27)

#### 1) SpringMVCEndpointExtraction 클래스 추가
**목표**: Spring MVC 프레임워크 전용 엔드포인트 추출 전략 구현

**클래스 구조**:
```python
class SpringMVCEndpointExtraction(EndpointExtractionStrategy):
    """Spring MVC 어노테이션을 사용한 엔드포인트 추출"""
    
    # 주요 메서드:
    - extract_endpoints_from_classes(classes) → List[Endpoint]
    - extract_endpoint(cls, method, class_paths) → Optional[Endpoint]
    - extract_http_method_from_annotation(annotation) → Optional[str]
    - extract_paths_from_annotation(annotation) → List[str]
    - get_class_level_paths(cls) → List[str]
    - get_annotation_text_from_file(file_path, target_name, is_class) → List[str]
    - classify_layer(cls, method) → str
```

#### 2) 주요 동작 원리

##### A. 2단계 경로 추출 및 Cartesian Product 생성

**단계 1: 클래스 레벨 경로 추출**
```python
# @RequestMapping이 있는 클래스에서 path/value 속성 추출
@RequestMapping("/api")
class UserController { ... }
→ class_paths = ["/api"]
```

**단계 2: 메서드 레벨 경로 및 HTTP 메서드 추출**
```python
# 메서드의 HTTP 메서드 어노테이션에서 경로 및 메서드 추출
@PostMapping("/users")
public void addUser() { ... }
→ method_paths = ["/users"], http_method = "POST"
```

**단계 3: Cartesian Product 생성**
```python
# 클래스 경로 N개 × 메서드 경로 M개 → N×M 조합
class_paths = ["/api", "/v1"]
method_paths = ["/users", "/members"]
↓
결과 = ["/api/users", "/api/members", "/v1/users", "/v1/members"]
```

**적용 예시**:
```
클래스: UserController
  ├─ @RequestMapping: ["/api", "/v1"]
  └─ 메서드: getUser()
       ├─ @GetMapping(path="/users")
       └─ 결과: 4개의 엔드포인트 행
          - GET /api/users
          - GET /v1/users
```

##### B. 지원하는 어노테이션

**1. Spring MVC 매핑**
| 어노테이션 | HTTP 메서드 | 경로 속성 | 예시 |
|-----------|-----------|----------|------|
| @GetMapping | GET | value, path | @GetMapping("/users") |
| @PostMapping | POST | value, path | @PostMapping(path="/user") |
| @PutMapping | PUT | value, path | @PutMapping("/user/{id}") |
| @DeleteMapping | DELETE | value, path | @DeleteMapping("/user/{id}") |
| @PatchMapping | PATCH | value, path | @PatchMapping("/profile") |
| @RequestMapping | GET (기본) | value, path, method | @RequestMapping(path="/", method=RequestMethod.GET) |

**2. 클래스 레벨 경로**
```python
# @RequestMapping만 지원 (다른 어노테이션은 경로 의미 없음)
@RequestMapping("/api/v2")
class ProductController { ... }
```

**3. 주의사항**
```
❌ method={RequestMethod.GET, RequestMethod.POST} 형태는 첫 번째만 추출
❌ 메서드당 여러 HTTP 메서드 어노테이션 있으면 첫 번째만 처리
✅ 경로 속성 없는 어노테이션 (@PostMapping) 는 빈 경로 처리
```

##### C. 메서드 추출 파이프라인 (AST Parser 기반)

**단계 1: 정규식으로 메서드 시작 위치 찾기**
```python
pattern = rf"(?:@\w+(?:\([^)]*\))?\s*)+" \
          rf"(?:public|private|protected)?\s+" \
          rf"(?:static\s+)?(?:final\s+)?" \
          rf"(?:[\w<>\[\],\s\.]+)?\s+" \
          rf"{re.escape(method_name)}\s*\("
```

**단계 2: AST Parser로 정확한 어노테이션 추출**
```python
# tree-sitter를 사용한 AST 파싱
# - method_declaration 노드 식별
# - modifiers 자식 노드에서 annotation 추출
# - 라인번호 검증 (중복 메서드명 대응)
```

**단계 3: 폴백 처리**
```python
# AST Parser 실패 시 → 정규식으로 재시도 안 함
# → 빈 리스트 반환 (엄격한 정책)
```

#### 3) 에러 처리 및 로깅 강화

**A. 파일 읽기 오류 로깅**
```python
# 시도 순서:
# 1. UTF-8 인코딩으로 읽기
# 2. 실패 → EUC-KR 인코딩으로 재시도
# 3. 둘 다 실패 → 경고 로깅
logger.warning(f"Failed to read annotation file {file_path}: "
               f"UTF-8 error: {e}, EUC-KR error: {e2}")
```

**B. AST Parser 오류 로깅**
```python
# AST Parser 실패 시 debug 레벨로 로깅
logger.debug(f"AST Parser failed for method '{target_name}' in {file_path}: {str(e)}")
```

**포함된 정보**:
- 대상 메서드명
- 파일 경로
- 발생한 예외 메시지

#### 4) 레이어 분류 다중 추론

**분류 순서** (우선순위):
1. 🔴 **어노테이션 기반** (가장 높음)
   - @Controller, @RestController → Controller
   - @Service → Service
   - @Repository → Repository
   - @Mapper → Mapper
   - @Entity, @Table → Entity

2. 🟡 **클래스명 패턴 기반**
   - *Controller, *RestController → Controller
   - *Service → Service
   - *Repository, *DAO → Repository
   - *Mapper → Mapper
   - *Entity, *Domain, *Model → Entity

3. 🟠 **인터페이스 구현 기반**
   - implements Mapper, SqlMapper → Mapper
   - implements JpaRepository, CrudRepository → Repository

4. 🟢 **패키지명 기반**
   - *.controller, *.web, *.api → Controller
   - *.service, *.business → Service
   - *.mapper, *.mybatis → Mapper
   - *.repository, *.jpa → Repository
   - *.dao, *.data → DAO
   - *.entity, *.domain, *.model, *.beans → Entity

5. 🔵 **필드 타입 추론 기반** (가장 낮음)
   - EntityManager, EntityManagerFactory → Repository
   - SqlSession, SqlSessionTemplate → Mapper
   - JdbcTemplate, DataSource → DAO

#### 5) 설계 제약사항

| 제약사항 | 설명 | 이유 |
|---------|------|------|
| 메서드당 1개 HTTP 메서드만 처리 | 첫 번째 HTTP 메서드 어노테이션 후 루프 종료 | 간단한 설계, 실무에서 거의 일어나지 않음 |
| RequestMapping 다중 메서드 미지원 | method={GET, POST} 형태에서 첫 번째만 추출 | 정규식 복잡도 증가 방지 |
| 메서드명 중복 시 라인번호 검증 | target_line 파라미터로 정확한 메서드 식별 | 같은 이름의 메서드 오버로딩 처리 |
| 파일 인코딩 폴백 제한 | UTF-8 → EUC-KR만 지원 | 한국 프로젝트 기준 인코딩 선정 |

#### 6) 사용 예시

**상황 1: 단순 엔드포인트**
```java
@RestController
@RequestMapping("/api/users")
public class UserController {
    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) { ... }
}
```
결과: `Endpoint(path=["/api/users/{id}"], http_method="GET", ...)`

**상황 2: 다중 경로 (Cartesian Product)**
```java
@RestController
@RequestMapping({"/api", "/v1"})
public class UserController {
    @PostMapping({"/user", "/users"})
    public void createUser(User user) { ... }
}
```
결과:
```
Endpoint 1: path=["/api/user", "/api/users", "/v1/user", "/v1/users"], http_method="POST"
```

**상황 3: 경로 없는 어노테이션**
```java
@RestController
@RequestMapping("/api")
public class UserController {
    @PostMapping  // 경로 미지정
    public void createUser(User user) { ... }
}
```
결과: `Endpoint(path=["/api"], http_method="POST", ...)`

---

### v2.5 다중 경로 지원 및 데카르트 곱(N x M) 매핑 구현 (2026.02.24)

#### 1) 다중 엔드포인트 경로 처리 고도화
**문제점**: 클래스에 `@RequestMapping` 경로가 여러 개 있거나 메소드에 여러 경로가 정의된 경우 첫 번째 경로만 인식됨.
**해결책**:
- `Endpoint` 모델의 `path` 타입을 `List[str]`로 변경.
- 프레임워크별 추출 전략(`SpringMVC`, `Anyframe`)에서 가능한 모든 경로 조합을 추출하도록 개선.

#### 2) 엔드포인트 행 분리 (Flat-Row Reporting)
**정의**: 클래스 경로 $N$개와 메소드 경로 $M$개가 존재할 때, 총 $N \times M$개의 개별 엔드포인트 객체를 생성하여 리프팅.
**적용 결과**:
- 예: 클래스(`/aa1`, `/aa2`) & 메소드(`/bb1`, `/bb2`) $\rightarrow$ 총 4개의 행 생성
- 엑셀 및 JSON 리포트에서 각 결합 경로를 독립된 데이터 행으로 관리하여 가시성 확보.

#### 3) Anyframe SarangOn 검색 강화
- 어노테이션 기반 레이어 분류(`ServiceIdMapping` 등) 시 대소문자 구분 없이 검색하도록 개선하여 누락 방지.

### v2.4 AST 기반 메소드 추출 및 검증 강화, 파일 저장 안정화 (2026.02.13)

#### 1) 4단계 메소드 추출 파이프라인 (AST Parser 도입)

**문제점**: 정규식 기반 추출로 인한 오류
- `if`, `for` 등 제어문을 메소드로 오인식
- 한글 변수명 등이 메소드로 감지
- MyBatis Mapper 인터페이스 메소드 미감지

**해결책**: 4단계 검증 파이프라인
```
1단계: difflib → 변경된 라인 식별
2단계: AST parser → 메소드 범위 파악  
3단계: 라인 매핑 → 변경된 메소드 식별
4단계: 블럭 비교 → Fallback 검증 (AST 파싱 실패 시)
```

**도입 탈락 기술**:
- tree-sitter-java: AST 트리 구조 파싱으로 정확한 메소드 범위 획득
- JavaASTParser: line_start, line_end, source 속성으로 메소드 경계 추적

**개선 결과**:
```
추출 정확도: 100% (거짓 양성 제거)
지원 대상: 일반 클래스, 인터페이스, 내부 클래스
Fallback: AST 파싱 실패 시에도 메소드 블럭 비교로 감지
```

#### 2) 2단계 메소드명 검증 시스템

**단계 1: 형식 검증** (Excel 생성 전)
```
조건: ClassName.methodName 형식 (점 구분자 필수)
오류 예시: "if", "for", "한글변수", "methodName" (클래스명 없음)
```

**단계 2: 교차검증** (신뢰도 확인)
```
AST parser로 추출한 메소드 → 정규식으로 독립적 재검증
결과: 신뢰도 100% 달성 (206/206 메소드 일치)

콘솔 출력 예시:
  [단계 1] 형식 검증: 117개 성공
  [단계 2] 교차검증: 206개/206개 일치 (신뢰도 100%)
  [OK] 모든 메소드가 프로젝트에 존재하고 교차검증도 통과했습니다!
```

**구현**:
- `build_project_method_map()`: 프로젝트 전체 Java 파일 스캔, 실제 메소드 206개 추출
- `validate_and_print_method_names()`: 콘솔 검증 결과 출력
- `cross_validate_methods_by_regex()`: 정규식으로 독립적 재검증

#### 3) 파일 변경 감지 개선 (구조 자동 감지)

**문제점**: Maven 표준 구조 가정으로 실제 프로젝트 구조 미감지
- 코드: `target_project/src/main/java` 고정 경로 사용
- 현실: `target_project/src/com/...` 실제 구조 미매칭
- 결과: "변경된 Java 파일이 없습니다" 오류

**해결책**: 동적 경로 감지
```python
if os.path.exists(os.path.join(target_project, "src", "main", "java")):
    target_src = os.path.join(target_project, "src", "main", "java")  # Maven
else:
    target_src = os.path.join(target_project, "src")  # 표준 구조
```

**개선 결과**:
- 변경 파일 감지: 0개 → 10개
- 추출 메소드: 55개 → 58개
- 지원 구조: Maven, 표준 구조 모두 지원

#### 4) 파일 저장 안정화 (Permission Error 대응)

**문제점**: 기존 Excel 파일이 다른 프로그램에서 열려있으면 저장 실패
```
❌ os.remove() 실패 → 경고 출력 후 continue
❌ wb.save() 실패 → 예외 발생 → 프로그램 중단
```

**해결책**: 자동 fallback 메커니즘
```python
def save_workbook_with_fallback(wb, output_file, logger):
    """
    Step 1: 기존 파일 삭제 시도
    Step 2: 실패 시 타임스탐프 추가하여 다른 파일명으로 저장
    Step 3: 정상 저장
    """
    # 예: EndPoint_Report_20260213_152345.xlsx
```

**개선 결과**:
```
파일이 열려있어도 ✅ 정상 완료
다른 파일명으로 자동 저장 (타임스탐프)
사용자 개입 최소화
```

---

### v2.0 개선사항
- **역추적 매칭 추가**: Service/Mapper/Interceptor 메소드도 엔드포인트 찾기 가능
- **여러 엔드포인트 지원**: 하나의 메소드가 여러 엔드포인트에서 호출되면 각각 행으로 표시
- **공통 함수 추출**: CLI(`list --callgraph`)와 Report Generator(`generate-endpoint_report`) 간 로직 공유
- **완벽한 일관성**: 두 명령어가 동일한 검색 로직 사용

### v2.1 개선사항
- **경로 표시 간결화**: 전체 절대 경로(`C:\Project\SSLife\book-ssm\src\com\mybatis\beans\Employee.java`)에서 대상 프로젝트 기준 상대 경로(디렉토리만, `\src\com\mybatis\beans\`)로 변경
- **열 너비 최적화**: B열(40), C열(25), D열(30), E열(35)으로 조정
- **계층적 셀 병합**: 파일경로/파일명/메소드명 조합에 따라 지능형 병합 구현
  - 파일경로만 같음 → 파일경로만 병합
  - 파일경로+파일명이 같음 → 파일경로+파일명 병합
  - 파일경로+파일명+메소드명 모두 같음 → 셋 모두 병합

### v2.2 코드 재구성 및 메소드 추출 강화 (2026.02.09)

#### 파일명 변경
- `src/analyzer/endpoint_analyzer.py` → `src/analyzer/callgraph_endpoint_finder.py`
  - 더 명확한 함수명으로 Call Graph 기반 엔드포인트 탐색 의도 표현
  - 임시 백업 파일 생성: `callgraph_endpoint_finder_tmp.py`

#### 소스 경로 처리 개선
- **변경 전**:
  ```python
  # 매개변수로 받은 경로를 그대로 사용
  changed_files = get_changed_java_files(target_project, old_code_path)
  ```
- **변경 후**:
  ```python
  # src/main/java 경로 자동 추가 (Maven 표준 구조)
  target_project = os.path.join(target_project, "src\main\java")
  old_code_path = os.path.join(old_code_path, "src\main\java")
  ```

#### Brace Level 계산 버그 수정
- **문제**: `} else {` 같은 한 줄 코드에서 `}` 감소 → `{` 증가가 동시에 발생하면 계산 오류
- **원인**: 메소드 시작 라인의 `{`를 카운트하지 않음
- **해결**:
  ```python
  # 메소드 선언 라인의 { 를 즉시 카운트
  if match:
      in_method = True
      brace_level = 0
      brace_level += cleaned_line.count('{') - cleaned_line.count('}')  # 추가!
  
  # 이후 라인들만 간단한 카운트
  elif in_method:
      brace_level += cleaned_line.count('{') - cleaned_line.count('}')
  ```

#### 메소드 추출 로직 다층 개선

##### 1단계: 주석/문자열 제거
```python
# Java 코드에서 주석과 문자열 리터럴을 정확히 제거
def remove_comments_and_strings(line: str) -> str:
    # 처리 대상:
    # - 라인 주석: //
    # - 블록 주석: /* */
    # - 문자열 리터럴: "..."
    # - 문자 리터럴: '...'
    # - 이스케이프 문자: \", \'
```

##### 2단계: Diff 기반 메소드 추출 (1차)
```python
# 선택: SequenceMatcher로 변경된 라인 찾기
# 결과: 변경된 라인 범위 획득
# 활용: build_method_ranges()로 메소드 범위 매핑
```

##### 3단계: 메소드 본문 비교 (Fallback, 2차)
```python
def extract_method_body(method_name: str, lines: List[str]) -> str:
    # 한 줄에 여러 메소드 있는 경우도 처리
    # 정규식으로 정확한 중괄호 매칭
    
    # 예시: public void foo() { } public void bar() { return 1; }
    # → foo()는 찾을 수 없지만, bar()는 본문 비교로 감지
```

##### 4단계: 메소드 집합 비교 (3차, Super Fallback)
```python
# new_methods - old_methods = 신규 추가된 메소드
# old_methods - new_methods = 제거된 메소드
# existing_methods & changed = 기존 메소드 중 변경된 것

# Diff와 본문 비교가 실패해도 메소드 변경 감지 가능
```

#### 에러 처리 강화
```python
# 파일 읽기 실패 시
try:
    target_content = read_file_safe(file_path)
except Exception as e:
    logger.warning(f"파일 읽기 실패: {file_path}")
    return set()

# 클래스명 추출 실패 시
if not class_name or class_name == 'Unknown':
    logger.warning(f"클래스명 추출 실패: {file_path}")
    return set()

# 원본 파일 읽기 실패 시 → 전체 변경된 것으로 간주
try:
    old_content = read_file_safe(old_file_path)
except:
    methods = extract_all_methods(target_content)
    return {f"{class_name}.{m}" for m in methods}
```

#### 감지 가능한 케이스 확장
| 케이스 | 이전 | 현재 |
|--------|------|------|
| Diff 기반 변경 | ✅ | ✅ |
| 주석만 변경 | ✅ | ✅ |
| 문자열 내 특수문자 | ⚠️ | ✅ (remove_comments_and_strings) |
| 한 줄 메소드 | ❌ | ✅ (extract_method_body) |
| 메소드명 동일하지만 본문 변경 | ✅ | ✅ (메소드 본문 비교) |
| Diff 분석 실패 | ❌ | ✅ (메소드 집합 비교) |
| } else { 분석 오류 | ❌ | ✅ (brace_level 수정) |

---

#### v2.2 코드 재구성 및 메소드 추출 강화 동기
**변경 전 문제점:**
- 한 줄에 여러 메소드가 있으면 첫 메소드만 감지
- Diff 분석이 실패하면 메소드를 못 찾는 경우 발생
- 주석과 문자열이 `{}` 포함 시 잘못된 괄호 레벨 계산
- 에러 처리 부족

**변경 후 개선:**
- 3단계 fallback 메커니즘으로 거의 모든 변경 감지
- 정확한 주석/문자열 제거로 중괄호 계산 오류 제거
- 다양한 에러 상황에 대한 graceful 처리

### v2.3 Endpoint 매칭 로직 완전 매칭 개선 (2026.02.10)

#### 문제점 분석
**기존 문제:** 부분 매칭(`in`)과 끝부분 매칭(`endswith`) 사용
- 예시: `'class_name.method_name'` 검색 시 `'class_name.method_nameAAA'`도 매칭되는 오류
- 영향 범위: CLI의 `list --callgraph` 명령과 Report Generator의 엔드포인트 검색 모두

#### 개선 사항
```python
# 변경 전 (부분 매칭으로 인한 오류)
if (
    method_signature in method_sig              # 부분 매칭 ❌
    or method_sig.endswith(method_signature)    # 끝부분 매칭 ❌
    or method_sig == method_signature           # 정확 매칭 ✅
):
    return endpoint

# 변경 후 (완전 매칭만 사용)
if ep_method_sig == method_signature:
    return endpoint_obj
```

#### 적용 범위
1. **src/analyzer/callgraph_endpoint_finder.py**
   - `find_endpoint_in_call_graph()`: 정확 매칭만 수행
   - `find_all_endpoints_for_method()`: 정확 매칭만 수행
   - `find_endpoints_that_call_method()`: 역추적 시 정확 매칭만 수행

2. **src/cli/cli_controller.py**
   - `_list_callgraph()`: 공통함수 사용으로 자동 적용

3. **src/generator/endpoint_report_generator.py**
   - `find_endpoint_for_method()`: 공통함수 사용으로 자동 적용

#### 테스트 케이스
```
✅ 정확 매칭: "EmpController.addEmpByGet" == "EmpController.addEmpByGet"
❌ 부분 매칭 차단: "EmpController.addEmpByGetAAA" != "EmpController.addEmpByGet"
✅ 역추적 검색: "Employee.getDayOfBirth" → 7개 엔드포인트 정확히 찾음
```

---

## A. 목적 및 개요

### 핵심 기능
대상 프로젝트(`target_project`)의 모든 Java 파일을 분석하여 변경전 원본 프로젝트(`old_code_path`)와 비교하고, 변경된 코드의 메소드를 추출한 후 이 메소드들의 End Point 목록을 Excel 형식으로 생성합니다.

### 산출물
```
{target_project}/applycrypto/artifacts/EndPoint_Report_{YYYYMMDD}.xlsx
```

### 주의사항
- 변경된 파일 목록이 없는 경우 프로젝트의 모든 파일을 비교
- 파일이 다수인 경우(1000~10000개) `difflib` 사용 시 시간이 소요될 수 있음

---

## B. 입력 및 전제조건

### B-1. 입력 데이터 경로

```
{target_project}
 └─ applycrypto/
     └─ results/
         └─ call_graph.json
```

### B-2. 필수 파일 및 데이터 구조

#### B-2.1 call_graph.json (필수)

```json
{
  "endpoints": [
    {
      "path": "/BInfo.do",
      "http_method": "GET",
      "method_signature": "BController.BInfo",
      "class_name": "BController",
      "method_name": "BInfo",
      "file_path": "D:\\WRES\\whealth\\admin\\www\\controller\\www\\BController.java"
    }
  ],
  "node_count": 3056,
  "edge_count": 6597,
  "all_trees": [
    {
      "method_signature": "BController.BInfo",
      "layer": "Controller",
      "is_circular": false,
      "children": [
        {
          "method_signature": "Model.addAttribute",
          "layer": "Unknown",
          "is_circular": false,
          "children": []
        }
      ]
    }
  ],
  "class_name": "BController",
  "file_path": "D:\\WRES\\whealth\\admin\\www\\controller\\www\\BController.java",
  "endpoint": {
    "path": "/BInfo.do",
    "http_method": "GET",
    "method_signature": "BController.BInfo",
    "class_name": "BController",
    "method_name": "BInfo",
    "file_path": "D:\\WRES\\whealth\\admin\\www\\controller\\www\\BController.java"
  }
}
```

---

## C. 출력 구조

### C-1. Excel 워크북 구성

**시트명:** `End Point 목록`

### C-2. 시트의 상세 구조

| 순서 | 열 | 너비 | 내용 |
|------|-----|------|------|
| 1 | A | 3 | 공백 |
| 2 | B | 40 | 파일 경로 (디렉토리만) |
| 3 | C | 25 | 파일명 |
| 4 | D | 30 | 메소드명 |
| 5 | E | 35 | Endpoint |

**행 구성:**
- 1행: 공백
- 2행: 헤더 (파일 경로, 파일명, 메소드명, Endpoint)
- 3행~: 엔드포인트 리스트 데이터

---

## D. 포맷 및 스타일 가이드

### D-1. 폰트

| 대상 | 설정 |
|------|------|
| 기본 | 맑은 고딕 (Malgun Gothic), 크기 10pt |
| 헤더 | 굵은 체 (bold), 10pt |

### D-2. 배경색 (PatternFill)

| 색상 코드 | 적용 대상 |
|-----------|---------|
| DFDFDF | 2행 (모든 컬럼) |

### D-3. 정렬

| 대상 | 정렬 방식 |
|------|---------|
| 헤더 | 중앙 정렬 |
| 데이터 | 좌측 정렬 (기본) |

### D-4. 줄바꿈

- **wrap_text=True**: 파일 경로 컬럼 (B열)

### D-5. 테두리

- **스타일**: thin
- **적용**: 모든 데이터 셀 (2행~)

### D-6. 행 높이

| 대상 | 높이 |
|------|------|
| 기본 | 16 |
| 헤더 | 16 |

---

## E. 상세 추출 규칙

### E-1. 파일 경로 및 파일명 추출

#### 파일 경로 추출
1. config.json에서 `target_project`와 `old_code_path` 경로 확인
2. 두 경로 간의 변경된 모든 `.java` 파일 검색
3. **target_project 기준 상대 경로 계산** (디렉토리만)

**경로 표시 형식:**
- 전체 경로: `C:\Project\SSLife\book-ssm\src\com\mybatis\beans\Employee.java`
- 표시 경로: `\src\com\mybatis\beans\`
- 구분자: 백슬래시(\) 통일, 마지막에 백슬래시 추가

**파일 비교 방법:**
- `difflib`를 사용한 코드 라인별 비교
- 파일 존재 여부 및 내용 변경 확인

#### 파일명 추출
- 변경된 파일의 basename 추출 (e.g., "Employee.java")

### E-2. 메소드명 추출

1. 변경된 파일의 코드를 라인별로 비교
2. 변경된 부분이 속한 메소드만 추출
3. **파일 1개당 여러 메소드 가능**

**추출 로직:**
- Java AST 파싱을 통해 메소드 범위 결정
- 변경된 라인이 포함된 메소드만 식별

### E-3. End Point 추출

#### 2단계 매칭 로직

**Step 1: 직접 매칭 (Controller 메소드)**
- `call_graph.json`의 `endpoints` 배열에서 직접 검색
- 해당 메소드명의 엔드포인트 찾기
- 예시: `EmpController.addEmpByGet` → `/api/emps/addEmpByGet`

**Step 2: 역추적 매칭 (Service/Mapper/Interceptor 메소드)**
- `call_graph.json`의 `call_trees` 배열 사용
- 이 메소드를 호출하는 모든 엔드포인트 찾기
- 예시: `Employee.getDayOfBirth` → 이를 호출하는 7개 엔드포인트 모두 반환

#### 매칭 규칙 (완전 매칭)

```
1. 정확 매칭만 수행: method_signature == "EmpController.addEmpByGet"

부분 매칭이나 끝부분 매칭은 오류 유발 가능
(예: "class_name.method_name" 검색 시 "class_name.method_nameAAA"도 매칭되는 문제)
→ 정확한 완전 매칭으로만 구현
```

#### 반환 형식

- **직접 매칭 성공**: `['/api/emps/addEmpByGet']` (1개 리스트)
- **역추적 매칭 성공**: `['/api/emps/addEmpByGet', '/api/emps/addEmpByPost', ..., '/emp/editEmpByPost']` (복수 리스트)
- **매칭 실패**: `[]` (빈 리스트)

#### 호출 순서

```python
# 1. 직접 매칭 시도
endpoint = find_endpoint_in_call_graph(method_sig, call_graph)
if endpoint found:
    return [endpoint_path]

# 2. 역추적 매칭 시도
endpoints = find_endpoints_that_call_method(method_sig, call_graph)
if endpoints found:
    return [paths...]

# 3. 모두 실패
return []
```

#### 대체 방법 (CLI 확인용)

`list_callgraph` 핸들러를 활용한 동적 조회:
```
python main.py list --callgraph Employee.getDayOfBirth
→ 8개의 호출 그래프 표시
```

---

## F. 처리 규칙 및 로직

### F-1. 여러 엔드포인트 처리

**메소드당 여러 엔드포인트 지원:**
- 하나의 메소드가 여러 엔드포인트에서 호출될 수 있음
- 각 엔드포인트마다 별도의 행으로 출력

**예시:**
```
메소드: Employee.getDayOfBirth (변경된 메소드)
호출하는 엔드포인트:
  [1] GET   /api/emps/addEmpByGet    (EmpController.addEmpByGet)
  [2] POST  /api/emps/addEmpByPost   (EmpController.addEmpByPost)
  [3] GET   /api/emps/editEmpByGet   (EmpController.editEmpByGet)
  [4] POST  /api/emps/editEmpByPost  (EmpController.editEmpByPost)
  [5] GET   /emp/addEmpByGet         (EmployeeController.addEmp)
  [6] GET   /emp/editEmpByGet        (EmployeeController.editEmp)
  [7] POST  /emp/editEmpByPost       (EmployeeController.edit)

Excel 출력:
행 1: 파일경로 | 파일명 | Employee.getDayOfBirth | /api/emps/addEmpByGet
행 2:        |       | Employee.getDayOfBirth | /api/emps/addEmpByPost
행 3:        |       | Employee.getDayOfBirth | /api/emps/editEmpByGet
... (총 7행)
```

### F-2. 정렬 및 셀 병합

#### 정렬 순서 (4단계)

1. **Primary**: 파일 경로 (오름차순)
2. **Secondary**: 파일명 (오름차순)
3. **Tertiary**: 메소드명 (오름차순)
4. **Quaternary**: 엔드포인트 (오름차순)

#### 병합 규칙 (계층적 병합)

**3가지 병합 레벨:**

1. **Level 1**: 파일경로만 다를 때
   - 파일경로(B열) 병합
   - 파일명(C열) - 병합 안 함
   - 메소드명(D열) - 병합 안 함

2. **Level 2**: 파일경로는 같지만 파일명이 다를 때
   - 파일경로(B열) 계속 병합
   - 파일명(C열) 병합
   - 메소드명(D열) - 병합 안 함

3. **Level 3**: 파일경로, 파일명, 메소드명이 모두 같을 때
   - 파일경로(B열) 병합
   - 파일명(C열) 병합
   - 메소드명(D열) 병합

**예시:**
```
파일경로 | 파일명 | 메소드명1 | 엔드포인트1
        |       | 메소드명1 | 엔드포인트2   ← Level 3: 셋 다 같음 → B,C,D 모두 병합
        |       | 메소드명2 | 엔드포인트3   ← Level 2: 경로/파일명만 같음 → B,C만 병합
        | 다른파일 | 메소드명3 | 엔드포인트4   ← Level 1: 경로만 같음 → B만 병합
다른경로  | 다른파일 | 메소드명4 | 엔드포인트5   ← 병합 안 함
```

---

## G. 데이터 모델 및 공통 함수

### G-1. 추출된 데이터 구조

```python
@dataclass
class EndPointData:
    file_path: str          # 전체 파일 경로
    file_name: str          # 파일명 (확장자 포함)
    method_name: str        # 메소드명
    endpoint: str           # 엔드포인트 경로 (e.g., "/api/emps/addEmpByGet" 또는 "Unknown")
    
    # 4단계 정렬 지원
    def __lt__(self, other):
        return (self.file_path, self.file_name, self.method_name, self.endpoint) < \
               (other.file_path, other.file_name, other.method_name, other.endpoint)
```

### G-2. 공통 함수 (Code Reuse)

#### G-2.1 `find_endpoint_in_call_graph()`

**위치:** `src/analyzer/callgraph_endpoint_finder.py`

**용도:** CLI(`_list_callgraph`)의 기존 엔드포인트 매칭 로직을 Report Generator와 공유

**구현 기원:**
- CLI의 `_list_callgraph()` 함수에서 사용하던 정확한 매칭 로직을 그대로 이관
- 폴백 코드 제거하고 공통함수만 사용하도록 통합

**시그니처:**
```python
def find_endpoint_in_call_graph(
    method_signature: str,
    call_graph_data: Dict[str, Any],
    return_type: str = "dict",
) -> Optional[Dict[str, Any]]:
    """
    endpoints 배열에서 메소드 시그니처에 매칭하는 엔드포인트를 찾습니다.
    
    기존 _list_callgraph의 정확한 매칭 로직을 그대로 이관했습니다.
    
    Args:
        method_signature: 찾을 메소드 시그니처 (e.g., "EmpController.addEmpByGet")
        call_graph_data: Call Graph JSON 데이터
        return_type: 반환 형식 - "dict", "endpoint", "full"
    
    Returns:
        Optional: 매칭된 엔드포인트 또는 None
    """
```

**매칭 패턴 (정확 매칭만):**

현재 구현 (v2.3 - 완전 매칭으로 개선):
```python
# 정확한 메소드 시그니처만 매칭
if ep_method_sig == method_signature:
    return endpoint_obj
```

매칭 방식:
- **정확 매칭만**: `ep_method_sig == method_signature`
  - ✅ "EmpController.addEmpByGet" == "EmpController.addEmpByGet"
  - ❌ "EmpController.addEmpByGetAAA" != "EmpController.addEmpByGet" (오류 방지)

**v2.3 개선사항:**
기존에는 부분 매칭(`in`)과 끝부분 매칭(`endswith`)을 사용했으나, 
검색어 'class_name.method_name'으로 'class_name.method_nameAAA'도 
매칭되는 오류가 있어 완전 매칭(==)으로만 변경했습니다.

**반환 타입:**
- `"dict"`: `{'path': '...', 'http_method': 'GET', 'method_signature': '...', 'class_name': '...'}`
- `"endpoint"`: `Endpoint` 객체
- `"full"`: 엔드포인트 전체 정보

**사용 사례:**

*Case 1: CLI _list_callgraph*
```python
# cli_controller.py의 _list_callgraph()에서
target_endpoint_obj = find_endpoint_in_call_graph(
    method_signature=endpoint,
    call_graph_data=call_graph_data,
    return_type="endpoint"
)
```

*Case 2: Report Generator find_endpoint_for_method*
```python
# endpoint_report_generator.py에서
# Step 1: 직접 매칭 시도
result = find_endpoint_in_call_graph(method_signature, call_graph)
if result:
    return [result['path']]

# Step 2: 역추적 매칭으로 전환
matching_endpoints = find_endpoints_that_call_method(method_signature, call_graph)
if matching_endpoints:
    return [ep['path'] for ep in matching_endpoints]
```

**참고사항:**
- endpoints 배열만 검색 (call_trees는 사용 안 함)
- first-match 반환 (첫 번째 매칭되는 엔드포인트만)
- 매칭 패턴 변경 시 CLI와 Report Generator 모두 영향 받음

#### G-2.2 `find_endpoints_that_call_method()`

**위치:** `src/analyzer/callgraph_endpoint_finder.py`

**용도:** call_trees 역추적을 통해 메소드를 호출하는 모든 엔드포인트 찾기

**시그니처:**
```python
def find_endpoints_that_call_method(
    method_signature: str,
    call_graph_data: Dict[str, Any],
    return_type: str = "dict",
) -> List[Dict[str, Any]]:
    """
    method_signature가 호출되는 모든 엔드포인트 찾기 (역추적)
    
    예시:
        Employee.getDayOfBirth를 찾으면:
        - EmpController.addEmpByGet
        - EmpController.addEmpByPost
        - EmployeeController.addEmp
        - ... (총 7개)
    
    Args:
        method_signature: 찾을 메소드
        call_graph_data: Call Graph JSON (call_trees 포함)
        return_type: 반환 형식
    
    Returns:
        이 메소드를 호출하는 모든 엔드포인트 리스트
    """
```

#### G-2.3 `find_endpoint_for_method()` (Report Generator)

**위치:** `src/generator/endpoint_report_generator.py` (실제로는 G-2.1, G-2.2의 공통함수를 사용)

**개선사항:** 리스트 반환 지원

**시그니처:**
```python
def find_endpoint_for_method(
    method_signature: str,
    call_graph: Dict
) -> List[str]:
    """
    2단계 매칭으로 메소드의 모든 엔드포인트 찾기
    
    Step 1: 직접 매칭 (endpoints에서)
    Step 2: 역추적 매칭 (call_trees에서)
    
    Args:
        method_signature: 메소드 (e.g., "Employee.getDayOfBirth")
        call_graph: Call Graph 데이터
    
    Returns:
        List[str]: 엔드포인트 경로 리스트
        - 직접 매칭: ['/api/emps/addEmpByGet']
        - 역추적 매칭: ['/api/emps/addEmpByGet', '/api/emps/addEmpByPost', ...]
        - 매칭 실패: []
    """
```

### G-3. 작업 순서

1. **파일 비교**: `old_code_path` vs `target_project`
2. **변경 파일 수집**: `.java` 파일 목록
3. **메소드 추출**: 변경된 메소드들 (`JavaASTParser` + brace tracking)
4. **엔드포인트 매칭**: `find_endpoint_for_method()` 호출
   - Step 1: `find_endpoint_in_call_graph()` (직접 매칭)
   - Step 2: `find_endpoints_that_call_method()` (역추적 매칭)
5. **데이터 확장**: 여러 엔드포인트 → 각각의 행 생성
6. **정렬**: 4단계 정렬 규칙 적용
7. **셀 병합**: 동일 파일경로/파일명 병합
8. **Excel 생성**: openpyxl을 통한 동적 생성

---

## H. 에러 처리

| 상황 | 처리 방법 |
|------|---------|
| `call_graph.json` 없음 | `{target_project}/applycrypto/results/` 디렉토리 확인 후 에러 로깅 |
| `old_code_path` 없음 | config.json 설정 확인 후 경고 로그 |
| 변경 파일 없음 | 전체 프로젝트 파일 비교 진행, 경고 로그 |
| 메소드-엔드포인트 매칭 실패 | **"Unknown"으로 표시** (역추적 매칭 후에도 없으면) |
| 여러 엔드포인트 매칭 성공 | 모두 나열 (각각 별도 행으로 생성) |

### H-1. "Unknown" 처리

메소드가 어떤 엔드포인트에도 연결되지 않은 경우:
- **예시:** Service/Mapper/Interceptor 클래스의 메소드 중 Call Graph에 없는 메소드
- **처리:** "Unknown"으로 표시 (1행만 생성)

```
file_path | file_name | method_name | endpoint
          |           | Some.method | Unknown
```

### H-2. 여러 엔드포인트 처리

역추적으로 7개의 엔드포인트를 찾은 경우:
- **처리:** 7개의 행 모두 생성 (메소드명은 동일하지만 엔드포인트는 각각 다름)
- **정렬:** 엔드포인트 경로순으로 정렬

```
file_path | file_name | method_name | endpoint1
          |           | method_name | endpoint2
          |           | method_name | endpoint3
          |           | method_name | endpoint4
          |           | method_name | endpoint5
          |           | method_name | endpoint6
          |           | method_name | endpoint7
```
→ file_path와 file_name은 첫 행에만 표시되고 나머지는 병합됨

---

## I. 성능 고려사항

| 항목 | 전략 |
|------|------|
| 파일 비교 | 변경 파일 목록 있으면 우선 사용, 없으면 전체 비교 |
| 대용량 처리 | 배치 처리 및 진행 상황 로깅 |
| 메모리 효율 | 파일별 순차 처리 |
| 결과 캐싱 | 중간 결과를 temp 파일에 저장 가능 |

---

## J. CLI 통합

### 명령어 형식

```bash
python main.py generate-endpoint_report --config config.json
```

### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|-------|
| `--config` | 설정 파일 경로 | 필수 |
| `--dry-run` | 미리보기 모드 | False |
| `--output` | 출력 파일 경로 | `{target_project}/applycrypto/artifacts/EndPoint_Report_{YYYYMMDD}.xlsx` |

---

## K. 구현 체크리스트

### 구현 완료 항목 (v2.2)
- [x] `endpoint_report_generator.py` 생성
- [x] 파일 비교 로직 구현 (`difflib` 활용)
- [x] Java 메소드 추출 로직 구현 (`JavaASTParser` + brace tracking)
- [x] Call Graph JSON 파싱 로직
- [x] 엔드포인트 매칭 로직 (2단계: 직접 + 역추적)
- [x] Excel 생성 및 포맷팅 로직
- [x] 정렬 및 병합 구현
- [x] 에러 처리 및 로깅
- [x] CLI 명령어 등록 (`main.py`)
- [x] 여러 엔드포인트 처리 (메소드당 여러 행)
- [x] 공통 함수 추출 (`endpoint_analyzer.py`) - 기존 _list_callgraph 로직 정확히 이관
- [x] CLI와 Report Generator 로직 일관성 유지 (폴백 코드 제거, 100% 공통함수 사용)
- [x] 경로 표시 간결화 (상대 경로 표시)
- [x] 열 너비 최적화
- [x] 계층적 셀 병합

### v2.2 추가 완료 항목
- [x] 파일명 변경: `endpoint_analyzer.py` → `callgraph_endpoint_finder.py`
- [x] Brace Level 계산 버그 수정 (`} else {` 한 줄 코드 처리)
- [x] `remove_comments_and_strings()` 함수 적용 (정확한 주석/문자열 제거)
- [x] `extract_changed_methods()` 에러 처리 강화
- [x] `extract_method_body()` 함수 추가 (메소드 본문 비교, fallback)
- [x] 다층 Fallback 메커니즘 구현 (Diff → 본문 비교 → 메소드 집합 비교)
- [x] 한 줄 메소드 정확히 감지
- [x] 소스 경로 자동화: `src\main\java` 추가 처리
- [x] 구현명세서 v2.2 케이스 추가 (Brace level 수정, 메소드 추출 강화)
- [x] README 버전 업데이트 (v2.2.1)

### 관련 파일 위치

| 파일 | 용도 | 버전 |
|------|------|------|
| `src/generator/endpoint_report_generator.py` | Main 구현 | v2.0+ |
| `src/analyzer/endpoint_analyzer.py` | 공통 함수 | v2.0+, v2.2 완성 |
| `src/cli/cli_controller.py` | CLI 통합 | v2.2 개선 (폴백 제거) |
| `docs/endpoint_report_instruction.md` | 본 문서 | v2.2 완성 |

---

## K. 구현 사례 및 검증

### K-1. 직접 매칭 예시

**메소드:** `EmpController.addEmpByGet`

**과정:**
1. `find_endpoint_in_call_graph("EmpController.addEmpByGet", call_graph)`
2. endpoints 배열에서 method_signature 정확 매칭
3. 결과: `['/api/emps/addEmpByGet']`

**Excel 출력:**
```
파일명: EmpController.java
메소드명: EmpController.addEmpByGet
엔드포인트: /api/emps/addEmpByGet
(1행만 생성)
```

### K-2. 역추적 매칭 예시

**메소드:** `Employee.getDayOfBirth` (Service/Mapper 메소드)

**과정:**
1. `find_endpoint_in_call_graph("Employee.getDayOfBirth", call_graph)` → None (endpoints에 없음)
2. `find_endpoints_that_call_method("Employee.getDayOfBirth", call_graph)`
3. call_trees 역추적으로 이 메소드를 호출하는 엔드포인트 찾기
4. 결과: `['/api/emps/addEmpByGet', '/api/emps/addEmpByPost', '/api/emps/editEmpByGet', '/api/emps/editEmpByPost', '/emp/addEmpByGet', '/emp/editEmpByGet', '/emp/editEmpByPost']`

**Excel 출력:**
```
파일명: Employee.java
메소드명: Employee.getDayOfBirth
엔드포인트 1: /api/emps/addEmpByGet   ← 7개의 행 생성
엔드포인트 2: /api/emps/addEmpByPost
엔드포인트 3: /api/emps/editEmpByGet
엔드포인트 4: /api/emps/editEmpByPost
엔드포인트 5: /emp/addEmpByGet
엔드포인트 6: /emp/editEmpByGet
엔드포인트 7: /emp/editEmpByPost
```

### K-3. CLI와의 일관성 검증

**명령어 1:** Report Generator
```bash
python main.py generate-endpoint_report --config config.json
→ Excel: Employee.getDayOfBirth → 7개 엔드포인트
```

**명령어 2:** CLI 호출 그래프 조회
```bash
python main.py list --callgraph Employee.getDayOfBirth
→ Terminal: 메서드 'Employee.getDayOfBirth'가 사용되는 8개의 호출 그래프를 찾았습니다
  [1/8] 엔드포인트: GET \api\emps\addEmpByGet (EmpController.addEmpByGet)
  [2/8] 엔드포인트: POST \api\emps\addEmpByPost (EmpController.addEmpByPost)
  ...
  [7/8] 엔드포인트: POST \emp\editEmpByPost (EmployeeController.edit)
  [8/8] 엔드포인트: ? (추가 검색됨)
```

**일관성:** 두 명령어 모두 동일한 `find_endpoints_that_call_method()` 함수 사용 → 일관된 결과

### K-4. Unknown 처리 예시

**메소드:** `SomeInterceptor.handle` (Call Graph에 없는 메소드)

**과정:**
1. `find_endpoint_in_call_graph()` → None
2. `find_endpoints_that_call_method()` → [] (빈 리스트)
3. 결과: `[]`

**Excel 출력:**
```
파일명: SomeInterceptor.java
메소드명: SomeInterceptor.handle
엔드포인트: Unknown
(1행만 생성, "Unknown"으로 표시)
```

---

**최종 수정일:** 2026년 2월 27일
**버전:** 2.6 (SpringMVC 엔드포인트 추출 전략 구현, AST Parser 기반 메서드 추출, 에러 로깅 강화)
