# 📋 클래스 사양서(Spec) 생성 구현 명세서

이 문서는 `src/generator/spec_generator.py`가 따라야 할 구현 명세서(Implementation Specification)입니다. 실제 코드 분석을 통해 정확한 기능, 데이터 흐름, 출력 구조를 명시합니다.

## A. 목적 및 개요

**핵심 기능**: Java 소스 파일을 JavaASTParser(tree-sitter 기반)로 파싱하여 정확한 클래스 메타정보, 메서드를 추출하고 Excel 사양서를 생성합니다. 각 클래스별로 개별 `.xlsx` 파일을 생성하거나, `--zip` 옵션으로 모두 하나의 ZIP 파일로 압축합니다.

**주요 개선사항** (v2.4+):
- ✅ **정규식 → AST 파싱**: JavaASTParser(tree-sitter) 기반으로 메서드 추출의 정확도 향상, 중복 제거
- ✅ **메타정보 확장**: 메서드 파라미터, 반환타입, 어노테이션, 예외 선언, 수정자(static/final/abstract) 자동 추출
- ✅ **캐싱 지원**: 파싱 결과를 `.applycrypto/cache/` 디렉터리에 캐시하여 성능 향상
- ✅ **모든 접근제한자 포함**: public, protected, private 메서드 모두 처리
- ✅ **Input Parameter 행 추가** (Row 6/11): 파라미터 시그니처 자동 표시
- ✅ **Return Type Generic 보존**: `List<Employee>`, `Map<String, Object>` 등 '<>' 문자 유지
- ✅ **Object 정의 명시화** (Row 2-3): Object ID (메서드명) + Description (JavaDoc 주석) 분리
- ✅ **메서드 시트 구조 최적화 (v2.4)**: 
  - 설계자: Row 1-9 (Object 정의 + 설계자 정보)
  - 개발자: Row 10-13 (개발자 정보 + 메서드 소스)
  - 병합 헤더: 1행, 5행, 10행 A-B열 병합 + 배경색 BFBFBF
  - 테두리 그룹화: (1-3) / (5-8) / (10-13)
  - 자동 높이: 3행, 8행, 13행 (wrap_text=True)
- ✅ **LLM 기반 메서드 요약** (오류 시에만 Row 8): `--llm` 옵션으로 8-점 아키텍처 분석 생성
- ✅ **LLM 응답 파싱 강화**: 마크다운 코드블럭 제거, JSON 파싱 오류 처리, 실패 시 "기능 없음" 반환
- ✅ **줄바꿈 지원**: \n 문자가 실제 줄바꿈으로 표시 (wrap_text 활성화)

**산출물**: 
- 개별 모드: `{target_project}/.applycrypto/artifacts/{ClassName}_spec.xlsx` (클래스당 1개 파일)
- ZIP 모드: `{target_project}/.applycrypto/artifacts/{ProjectName}_specs_{YYYYMMDD}.zip` (통합 ZIP)

## B. 입력 및 전제조건


### B-1. 입력 소스
=======
1. 입력: 현재 구현은 `config.target_project` 경로를 기준으로 프로젝트 내의 `ChangedFileList_*.txt`를 읽어 처리합니다. 직접적인 `--input-json` CLI 옵션은 구현되어 있지 않습니다. 함수형 API는 `generate_spec(config, zip_output=False)` 형태로 사용됩니다.
2. 파서: 정규식 및 텍스트 기반 추출을 주로 사용합니다. 완전한 Java AST를 요구하는 세밀한 추출은 코드에서 직접 제공하지 않으므로, 정밀한 AST 기반 추출이 필요하면 별도 전처리(JSON 변환 등)를 권장합니다.
3. 옵션: 코드 수준에서 제공되는 옵션은 `zip_output`(Boolean)뿐입니다. CLI 플래그로 문서에 열거된 `--controller-only`, `--include-source-snippet`, `--json-output` 등은 기본 배포에서 자동으로 지원되지 않습니다.
4. 인코딩: 파일 읽기는 UTF-8을 기본으로 기대합니다; 다른 인코딩 환경에서는 파일을 미리 UTF-8로 변환하거나 파일 읽기 로직을 확장해 주세요.

1. **파일 입력 (기본 모드)**
   - 소스: `config.json`의 `target_project` 경로
   - 파일 목록: `{target_project}/ChangedFileList_*.txt` 형식 파일에서 Java 파일 경로 읽음
   - 파일명 규칙: `ChangedFileList_<날짜>.txt` 또는 `ChangedFileList_<이름>.txt`
   - 형식: 한 줄에 한 파일 경로 (예: `src/main/java/com/example/UserService.java`)
   - 읽는 함수: `read_changedFileList_excel(target_project)` - 해당 경로의 모든 ChangedFileList 파일을 읽음

2. **JSON 입력 (향후 확장)**
   - 옵션: `--input-json <path>` 미지원이 현재 명세(동향 추적 필요)

### B-2. 파서 방식

**JavaASTParser (tree-sitter 기반) 파싱** ✅ 현재 구현
- **파서**: `src/parser/java_ast_parser.py` - tree-sitter-java 활용
- **입력**: Java 소스 코드 (Tree-sitter 파싱)
- **출력**: ClassInfo 객체 (메터정보 풍부)
  - `name`: 클래스명
  - `package`: 패키지명
  - `methods`: Method 객체 리스트
  - `annotations`: 클래스 어노테이션
  - `superclass` / `interfaces`: 상속/구현 정보

**Method 객체 구조** (AST 기반 추출):
```python
Method:
  - name: str (메서드명)
  - return_type: str (반환타입)
  - parameters: List[Parameter] (파라미터 정보)
  - annotations: List[str] (@RequestMapping 등)
  - exceptions: List[str] (throws IOException 등)
  - modifiers: List[str] (static, final, abstract)
  - access_modifier: str (public/protected/private)
  - source: str (메서드 본문)
```

**캐싱 지원**:
- CacheManager를 사용하여 파싱 결과를 `.applycrypto/cache/` 에 저장
- 반복 실행 시 성능 향상 (재파싱 불필요)

**인코딩 처리**:
- 우선순위: UTF-8 → EUC-KR → CP1252 → UTF-8 (errors='ignore')

## C. 출력 물 구조

### C-1. 시트 구성 (6개 시트)

각 클래스별 사양서는 다음 6개 시트로 구성됩니다:

1. **표제부** (Cover Sheet)
2. **Object정의** (Object Definition)  
3. **Object선언** (Object Declaration)
4. **login** (Method Template - 샘플)
5. **기타정의사항** (Other Definitions)
6. **변경이력** (Change History)

### C-2. 각 시트의 목적 및 내용

#### C-2.1 표제부 (Cover Sheet)

**목적**: 프로그램 전체에 대한 메타정보 및 개요 제공

**구조**:
- A1:F1: 제목 "프로그램 사양서" (배경색 BFBFBF, 굵은 글씨, 중앙정렬)
- A2:F2: 시스템명 (ⓐ), 시스템 (ⓑ), 서브시스템 (ⓒ) 
- A3:F3: 프로그램 ID (ⓓ), 작성자 (ⓔ), 작성일 (ⓕ)
- A4:F4: 프로그램명 (ⓖ) [B4:F4 병합]
- A5:F5: 개발 유형 (ⓗ), 프로그램 유형 (ⓘ)
- A6:F6: 프로그램 개요 (ⓙ) [B6:F6 병합, 행높이 150]

**셀 채우기 규칙**:
- F2: 프로젝트명 (target_project 이름 추출)
- F3: 클래스명 (예: UserService)
- F4: 패키지명 (예: com.example.service)
- 나머지 셀: 템플릿이므로 비우거나 기본값 사용

**포맷**:
- 열 너비: A=15, B=27, C=15, D=27, E=15, F=27
- 행 높이: 1행=20, 6행=150, 기타=16
- 폰트: 맑은 고딕 10pt
- 테두리: thin border (모든 셀)

#### C-2.2 Object정의 (Object Definition Sheet)

**목적**: 클래스 내 메서드 목록 및 기능 정의

**구조**:
- A1:D1: "ⓚ Object 리스트" (헤더, 배경색 BFBFBF, 중앙정렬, 병합)
- A2:D2: 컬럼 헤더 행
  - A2: "순번" 
  - B2: "Object ID"
  - C2: "주요 기능"
  - D2: "작업구분"

**데이터 행** (A3 이후):
- 순번: 1부터 순차 증가
- Object ID: 메서드명 (예: `getUser`)
- 주요 기능: 메서드의 설명(주석에서 추출한 첫 문장)
- 작업구분: (템플릿 - 일반적으로 비움)

**포맷**:
- 열 너비: A=10, B=30, C=40, D=15
- 행 높이: 기본 16
- 헤더 배경색: BFBFBF (굵은 글씨)
- 서브헤더 배경색: D9D9D9
- 줄바꿈 활성화: wrap_text=True

#### C-2.3 Object선언 (Object Declaration Sheet)

**목적**: 클래스 선언정보 (패키지, 상속, 구현 인터페이스, 어노테이션)

**구조**:
- A1:B1: "ⓛ Object 선언" (헤더, 배경색 BFBFBF, 중앙정렬, 병합)
- A2 이후: 다양한 선언 정보 기재

**기재 내용**:
- 패키지명: 정규식으로 추출한 package 값
- 클래스명: 추출한 class 이름
- extends: 상속 클래스 (있을 경우)
- implements: 구현 인터페이스 목록 (콤마 구분)
- 어노테이션: 클래스 레벨 어노테이션 (@Controller, @Service 등)

**포맷**:
- 열 너비: A=20, B=60
- 행 높이: 기본 16
- 헤더 배경색: BFBFBF

#### C-2.4 Method Sheet (메서드 시트) ✅ v2.4+ 업데이트 (2024.02.13)

**목적**: 특정 메서드에 대한 상세 스펙 (템플릿으로 login 메서드 예시 제공)

**구조 개선사항 (v2.4)**:
- ✅ **3행 구조 최적화**: 1-13행으로 정리 (기존 1-15행 → 신규 1-13행)
- ✅ **설계자 섹션 확장**: Object 정의 → Object ID, Description 명시화
- ✅ **테두리 그룹화**: (1-3) / (5-8) / (10-13) 3개 섹션별 테두리 구분
- ✅ **병합 헤더**: 1행, 5행, 10행 A-B열 병합 + 배경색 BFBFBF
- ✅ **행 높이 자동**: 3행, 8행, 13행 자동 높이 조절 (wrap_text=True)
- ✅ **줄바꿈 지원**: \n 문자가 실제 줄바꿈으로 표시 (wrap_text 활성화)

**설계자 섹션 (Rows 1-9)**:

##### Row 1: "■ Object 정의" 헤더
- 셀: **A1:B1** (병합)
- 배경색: BFBFBF (회색)
- 글꼴: 굵음 (Bold)
- 내용: "■ Object 정의"
- 행높이: 20
- 테두리: thin border (그룹 1/3)

##### Row 2-3: 기본 정보
- **Row 2**: 
  - A2: "○ Object ID" (BOLD)
  - B2: 메서드명 (예: `getUserInfo`)
  - 테두리: 적용
  
- **Row 3**: 
  - A3: "○ Description" (BOLD)
  - B3: JavaDoc 주석 (예: `사용자 정보를 조회합니다.`)
  - 행높이: 자동 (None)
  - 테두리: 적용 (그룹 1/3 마지막)

##### Row 4: 공백
- A4:B4 공백 및 테두리

##### Row 5: "■ 프로그램 구성별 상세 사양서 작성(설계자)" 헤더
- 셀: **A5:B5** (병합)
- 배경색: BFBFBF
- 글꼴: 굵음 (Bold)
- 내용: "■ 프로그램 구성별 상세 사양서 작성(설계자)"
- 행높이: 20
- 테두리: thin border (그룹 2/3)

##### Row 6-8: 설계자 입력 정보
- **Row 6**:
  - A6: "○ Input Parameter" (BOLD)
  - B6: 파라미터 시그니처 (예: `(String userId)`)
  - 테두리: 적용
  
- **Row 7**:
  - A7: "○ Return type" (BOLD)
  - B7: 반환타입 (예: `User`, `List<Employee>`) | Generic 타입 '>' 문자 보존 ✅
  - 테두리: 적용
  
- **Row 8**:
  - A8: "○ 상세 Logic" (BOLD)
  - B8: JavaDoc 주석 내용 + 메서드 메타정보
    ```
    Method: getUserInfo((String userId))
    Modifiers: public
    Annotations: @Override, @RequestMapping
    Exceptions: throws SQLException
    Description:
    사용자 정보를 조회합니다.
    ```
  - 행높이: 자동 (None)
  - 테두리: 적용 (그룹 2/3 마지막)
  - wrap_text: True (줄바꿈 지원)

##### Row 9: 공백
- A9:B9 공백

**개발자 섹션 (Rows 10-13)**:

##### Row 10: "■ 프로그램 구성별 상세 사양서 작성(개발자) → 프로그램 개발/테스트 완료 후 기술" 헤더
- 셀: **A10:B10** (병합)
- 배경색: BFBFBF
- 글꼴: 굵음 (Bold)
- 내용: "■ 프로그램 구성별 상세 사양서 작성(개발자) → 프로그램 개발/테스트 완료 후 기술"
- 행높이: 20
- 테두리: thin border (그룹 3/3)

##### Row 11-13: 개발자 입력 정보
- **Row 11**:
  - A11: "○ Input Parameter" (BOLD)
  - B11: 파라미터 시그니처 (예: `(String userId)`)
  - 테두리: 적용
  
- **Row 12**:
  - A12: "○ Return type" (BOLD)
  - B12: 반환타입
  - 테두리: 적용
  
- **Row 13**:
  - A13: "○ 상세 Logic" (BOLD)
  - B13: **메서드 소스 코드** (어노테이션 포함)
    ```
    public User getUserInfo(String userId) throws SQLException {
        return userDao.query(userId);
    }
    ```
  - 행높이: 자동 (None)
  - 테두리: 적용 (그룹 3/3 마지막)
  - wrap_text: True (줄바꿈 지원)

**데이터 매칭 규칙**:

| 항목 | 설계자 | 개발자 | 데이터 소스 |
|------|---------|---------|---------|
| **Object ID** | Row 2: B2 | - | `method['name']` |
| **Description** | Row 3: B3 | - | `method['comment']` (JavaDoc) |
| **Input Parameter** | Row 6: B6 | Row 11: B11 | `method['param_signature']` |
| **Return type** | Row 7: B7 | Row 12: B12 | `method['return_type']` |
| **상세 Logic** | Row 8: B8 | Row 13: B13 | B8: 메타정보 + JavaDoc / B13: 메서드 소스 |

**메서드별 시트 생성**:
- 각 메서드별로 동일한 구조의 시트가 동적으로 생성 (메서드명으로 시트명 설정)
- 예: "getUserInfo", "login", "saveData", "deleteUser" 등 메서드명으로 시트 자동 생성
- 모든 메타정보(파라미터, 반환타입, 어노테이션, 예외) 자동 채우기

**포맷 상세**:
- **열 너비**: A=20, B=100
- **폰트**: 맑은 고딕 10pt
- **정렬**: 좌측 정렬 (horizontal='left', vertical='center')
- **테두리 그룹**: 
  - (1-3): 기본 정보 섹션
  - (5-8): 설계자 섹션
  - (10-13): 개발자 섹션
- **배경색**: 1행, 5행, 10행 = BFBFBF (회색)
- **A열 스타일**: 모든 라벨 BOLD
- **자동 높이**: 3행, 8행, 13행 = None (자동 조절)

#### C-2.5 기타정의사항 (Other Definitions Sheet)

**목적**: 클래스 수준의 추가 정의 사항, 필드 목록 등

**구조**: 
- 클래스 필드 목록
- 필드명, 타입, 접근제어자, 기본값, 어노테이션 등 기재

**포맷**:
- 헤더 배경색: BFBFBF
- 줄바꿈 활성화: wrap_text=True

#### C-2.6 변경이력 (Change History Sheet)

**목적**: 클래스 변경 이력 기록

**구조**:
- 버전, 변경일, 변경자, 변경내용 등 컬럼

**포맷**:
- 헤더 배경색: BFBFBF
- 첫 행 행높이: 20
- 데이터 행 높이: 16 (wrap 가능)

## D. 상세 추출 규칙

### D-1. 패키지명 추출

**함수**: `extract_package(source)`  
**방식**: 정규식 `^\s*package\s+([\w.]+)\s*;`  
**예**: `package com.example.service;` → `com.example.service`  
**빈 경우**: 파일 경로로 추정 (파일의 디렉터리 경로 기반)

### D-2. 클래스명 추출

**함수**: `extract_class_declaration(source)`  
**방식**: 정규식으로 `class ClassName` 형태 검색  
**인식 문법**: `public/abstract/final class Name extends Parent implements I1,I2`  
**반환값**: (class_name, extends, implements_list, annotations_list)

### D-3. Extends / Implements 추출

**Extends**: 단수 (최대 1개)  
**Implements**: 콤마 구분 리스트 (여러 개 가능)  
**어노테이션**: 클래스 선언 직전 `@Annotation` 형태 추출 (최대 5개 최근 어노테이션)

### D-4. 메서드 추출 (JavaASTParser 기반)

**함수**: `JavaASTParser.extract_class_info(tree, file_path)` → ClassInfo.methods  
**방식**: Tree-sitter AST를 순회하여 메서드 노드 추출

**처리 흐름**:
1. `parse_file(file_path)` → Tree-sitter 파싱 트리 생성
2. `extract_class_info(tree, file_path)` → ClassInfo 객체 생성
3. ClassInfo.methods 에서 모든 Method 객체 추출
4. `_convert_method_objects_to_dict()` 에서 사전 형식 변환

**포함 대상** (필터링 없음):
- ✅ public, protected, private 모든 메서드 포함
- ✅ 생성자(constructor) 포함
- ✅ 정적 메서드(static) 포함
- ❌ Java 제어 키워드/람다 제외

**추출 정보**:
| 필드 | 설명 | 예시 |
|-----|------|------|
| name | 메서드명 | `login` |
| return_type | 반환타입 (제네릭 포함) | `String`, `List<User>`, `void` |
| parameters | 파라미터 정보 | `[{name: 'user', type: 'User', is_varargs: false}]` |
| param_signature | 파라미터 시그니처 | `User user, String password` |
| annotations | 어노테이션 리스트 | `["@RequestMapping", "@ResponseBody"]` |
| exceptions | throws 선언 | `["IOException", "SQLException"]` |
| modifiers | 수식어 | `["static", "final"]` |
| access_modifier | 접근제한자 | `public` / `protected` / `private` |
| source | 메서드 본문 | `{ ... }` (들여쓰기 정규화) |
| comment | 메서드 직전 주석 | Javadoc 또는 // 형식 |

### D-5. 메서드 메타정보 추출 (NEW)

**함수**: `_convert_method_objects_to_dict(methods, source)` ✅ NEW  
**목적**: JavaASTParser Method 객체를 spec_generator 호환 사전으로 변환

**처리 단계**:
1. **파라미터 추출**: Method.parameters → 파라미터 이름, 타입, varargs 여부
2. **파라미터 시그니처 생성**: `int id, String name` 형식으로 변환
3. **어노테이션 수집**: Method.annotations → 리스트 형식
4. **예외 선언 수집**: Method.exceptions → throws 리스트
5. **수식어 수집**: Method.modifiers → (static, final, abstract 등)
6. **메서드 본문 추출**: `extract_method_body(source, method_pos)` 호출
7. **JavaDoc 추출**: `extract_comment_before_method()` 호출

**반환 형식**:
```python
{
  'name': 'login',
  'return_type': 'String',
  'param_signature': 'User user, String password',  # NEW
  'parameters': [{'name': 'user', 'type': 'User'}],  # NEW
  'annotations': ['@RequestMapping', '@ResponseBody'],  # NEW
  'exceptions': ['IOException'],  # NEW
  'modifiers': ['static'],  # NEW
  'access_modifier': 'public',  # NEW
  'source': '{ ... }',
  'comment': 'User login method'
}
```

### D-6. 메서드 본문 추출

**함수**: `extract_method_body(source, brace_start)`  
**방식**: 중괄호 깊이 추적으로 메서드 전체 본문 추출

**정규화 규칙**:
1. 탭을 4스페이스로 확장 (`expandtabs(4)`)
2. 비어있지 않은 라인의 최소 들여쓰기 계산
3. 모든 라인에서 최소 들여쓰기 제거
4. 첫 본문 라인이 1 레벨(4스페이스)이 되도록 shift 조정

### D-7. 주석 추출

**함수**: 
- `extract_comment_before_method(source, method_start)`: 메서드 직전 주석
- `extract_class_javadoc(source, class_start_pos)`: 클래스 Javadoc

**형식**:
- Javadoc: `/** ... */` (HTML 태그 제거)
- 인라인: `// ...` 형식
- 첫 문단 우선 (요약)

### D-7. Import 추출

**함수**: `extract_imports(source)`  
**패턴**: `^\s*import\s+([\w.*]+)\s*;`  
**사용처**: Object선언 시트에서 의존성 정보 기재

## E. 처리 규칙 및 로직

### E-1. 진입점

**함수**: `generate_spec(config, zip_output=False)`

**주요 단계**:
1. `target_project`에서 `ChangedFileList_*.txt` 읽음 → Java 파일 목록 추출
2. 각 파일에 대해:
   - `read_java_file()`: 파일 읽기 (인코딩 우선순위 적용)
   - `extract_package()`, `extract_imports()`, `extract_class_declaration()`, `extract_methods()` 호출
   - 클래스 내부 어노테이션 병합 (`_get_class_body()` + 재발견)
3. `write_excel_for_class()` 호출하여 Excel 생성 또는 ZIP에 추가

### E-2. 워크북 생성

**함수**: `create_specification_workbook_from_scratch(first_changed_path)`

**절차**:
1. 빈 Workbook 생성
2. 기본 active sheet 제거
3. 6개 시트 생성:
   - `create_cover_sheet(wb)`
   - `create_object_definition_sheet(wb)`
   - `create_object_declaration_sheet(wb)`
   - `create_method_template_sheet(wb)`
   - `create_other_definitions_sheet(wb)`
   - `create_change_history_sheet(wb)`

### E-3. 시트 채우기

**함수**: `fill_cover_sheet(ws, class_name, file_path, source, package, first_changed_path)`

**채우는 항목**:
- F2: 프로젝트명 (`_extract_project_name()` 함수로 파일 경로에서 추출)
- F3: 클래스명
- F4: 패키지명
- 나머지: 비우거나 기본값

**기타 fill 함수**:
- `fill_object_definition_sheet(ws, methods, file_path)`: 메서드 목록
- `fill_object_declaration_sheet(ws, package, imports, annotations, extends, implements, source)`: 클래스 선언 정보

### E-4. 메서드 시트 생성

**함수**: `create_method_sheet(wb, method, source, template_ws, llm_provider=None)` ✅ v2.3+ 업데이트

**동작**:
- template_ws (login 시트)를 복제하여 새 시트 생성
- 메서드명으로 시트 제목 설정 (`_sanitize_sheet_title()` 사용하여 31자 제한, 금지 문자 처리)
- 메서드 정보 자동 채우기:

**설계자 섹션 (A5:B9)**:
- Row 5 (Object ID): 메서드명 → `ws['B5'] = method_name`
- Row 6 (Input Parameter) NEW: 파라미터 시그니처 → `ws['B6'] = param_signature` (없으면 "(없음)")
- Row 7 (Return Type): 반환타입 → `ws['B7'] = return_type` (Generic 타입 '<>' 보존)
- Row 8 (상세 Logic): 메서드 시그니처 + 수식어 + 어노테이션 + 예외 + JavaDoc
- Row 9 (참고사항) NEW: LLM 또는 휴리스틱 기반 메서드 요약 → `ws['B9'] = generate_method_summary(method_source, method_name, llm_provider)`
  - 포맷팅: 테두리 적용 (thin), wrap_text=True, vertical=top, 행높이 None(자동)

**개발자 섹션 (A12:B15)**:
- Row 12 (Object ID): 메서드명
- Row 13 (Input Parameter) NEW: 파라미터 시그니처
- Row 14 (Return Type): 반환타입
- Row 15 (상세 Logic): 전체 메서드 소스 (어노테이션 포함, 행높이 200)

### E-5. Excel 파일 저장

**함수**: `write_excel_for_class(class_name, file_path, ...)`

**저장 로직**:
- 개별 모드: `{out_dir}/{ClassName}_spec.xlsx`로 저장
- ZIP 모드: `zipfile.ZipFile`에 스트리밍 저장

**디렉터리**: `{target_project}/.applycrypto/artifacts/`

## F. CLI 옵션 및 설정

### F-1. 지원 옵션

**현재 지원** (v2.3+):
- `--zip`: ZIP 출력 활성화 (기본값: False)
- `--diff`: 변경된 파일만 처리 (기본값: False) | ChangedFileList 기준으로 필터
- `--llm` ✅ **NEW**: LLM 기반 메서드 요약 활성화 (기본값: False) | config.json의 `llm_provider` 설정 참조

**config.json에서 읽는 필드**:
- `target_project`: 프로젝트 루트 경로 (필수)
- `llm_provider`: LLM 프로바이더 (선택) | "watsonx_ai", "anthropic" 등 | `--llm` 사용 시 참고
- 기타 설정: 현재 사용 안 함

**사용 예시**:
```powershell
# 전체 사양서 (LLM 없음)
python main.py generate-spec --config config.json

# 전체 사양서 + LLM 메서드 요약
python main.py generate-spec --config config.json --llm

# 변경된 파일만 + LLM 요약 + ZIP
python main.py generate-spec --config config.json --diff --llm --zip
```

### F-2. 미지원 옵션 (향후 검토)

- `--input-json <path>`: JSON 입력 (구현되지 않음)
- `--output-dir <path>`: 출력 디렉터리 (고정값 사용)
- `--controller-only`: Controller 클래스만 처리 (미구현)
- `--col-widths`: 컬럼 너비 커스터마이징 (미구현)
- `--include-source-snippet N`: 소스 코드 스니펫 포함 (미구현)

## G. 포맷 및 스타일 가이드

### G-1. 폰트

- **기본**: 맑은 고딕 (Malgun Gothic), 크기 10pt
- **헤더**: 굵은 체 (bold)

### G-2. 배경색 (PatternFill)

| 용도 | 색상 코드 | RGB |
|------|---------|-----|
| 주요 헤더 | BFBFBF | 회색 |
| 서브헤더 | D9D9D9 | 밝은 회색 |

### G-3. 정렬

- **수평**: left (기본), center (헤더)
- **수직**: center (기본)
- **텍스트 줄바꿈**: True (긴 텍스트, 주석 등)

### G-4. 테두리

- **스타일**: thin
- **적용**: 모든 데이터 셀 (가독성 향상)

### G-5. 행 높이 (기본값)

| 행 | 높이 | 용도 |
|----|------|------|
| 제목행 | 20 | 섹션 헤더 |
| 데이터행 | 16 | 일반 데이터 |
| 상세설명 | 150-200 | 긴 설명 텍스트 |

### G-6. 열 너비 (기본값)

| 시트 | 열 | 너비 |
|-----|-----|------|
| 표제부 | A,C,E | 15 |
| | B,D,F | 27 |
| Object정의 | A | 10 |
| | B | 30 |
| | C | 40 |
| | D | 15 |
| Object선언 | A | 20 |
| | B | 60 |

## H. 예외 처리 및 오류 복구

### H-1. 파일 읽기 실패

**상황**: ChangedFileList 파일 읽음 실패 또는 Java 파일 접근 불가  
**처리**: `try-except` 블록으로 해당 파일 건너뛰고 다음 파일 처리

### H-2. 파싱 실패

**상황**: 정규식이 클래스 또는 메서드를 찾지 못함  
**처리**: 해당 구성 요소는 빈 값으로 처리하고 계속 진행

### H-3. 시트 제목 충돌

**상황**: 메서드명이 중복되거나 31자 초과  
**처리**: `_sanitize_sheet_title()` 함수로 정리
- 금지 문자 제거 (\ / ? * [ ])
- 31자 초과 시 절단
- 중복시 `_1`, `_2` 등 suffix 추가

### H-4. ZIP 생성 실패

**상황**: 권한 부족 또는 디스크 공간 부족  
**처리**: Exception 캐치, 오류 메시지 출력 후 계속

## I. 검증 및 테스트

### I-1. 단위 테스트 추천 항목

1. **패키지 추출**: 다양한 패키지 이름 형식 (깊은 경로, 특수문자 등)
2. **클래스 선언**: generic class, abstract, final, implements 다중 인터페이스
3. **메서드 추출**: 
   - 파라미터 있는/없는 메서드
   - 제네릭 반환타입 (List<String>, Map<String,Object> 등)
   - throws 선언이 있는 메서드
4. **들여쓰기 정규화**: 다양한 인덴트 스타일 (탭, 스페이스 혼용)
5. **주석 추출**: Javadoc, 인라인 주석, HTML 태그 포함

### I-2. 통합 테스트

1. **표준 프로젝트**: 소규모 Java 프로젝트(5~10 클래스)로 전체 파이프라인 검증
2. **ZIP 출력**: `--zip` 옵션으로 ZIP 파일 생성 및 내용 검증
3. **Excel 호환성**: 생성된 Excel 파일을 MS Excel, LibreOffice 등에서 열어 렌더링 확인

### I-3. 자동 검증 스크립트

- 생성된 시트 수 확인 (6개여야 함)
- 각 시트의 헤더 행 검증
- 데이터 행 수 확인 (메서드 수 = Object 리스트 행 수)

## J. 현재 구현과 명세의 비교

### J-1. 실제 구현 (현 시점)

| 항목 | 명세 상 | 실제 구현 |
|------|---------|---------|---------|
| 입력 형식 | JSON/파일 혼용 지원 | ChangedFileList_*.txt만 지원 | 동일 (ChangedFileList_*.txt) |
| **파서 방식** | **AST 파싱 (정확도 고)** | **정규식 기반 (속도 우위)** | **✅ JavaASTParser(tree-sitter) - AST 기반** |
| 메서드 추출 정확도 | 높음 | 중간 (중복 가능) | **✅ 높음 (중복 제거)** |
| 메서드 메타정보 | 풍부 (param, annotation, exceptions) | 기본 (name, return_type, source) | **✅ 확장 (모든 메타정보)** |
| 접근제한자 처리 | public/protected/private | public/protected만 | **✅ 모두 포함** |
| 파라미터 추출 | 상세 (name, type, varargs) | 텍스트 형식만 | **✅ 구조화된 객체** |
| 어노테이션 추출 | ✅ 메서드 어노테이션 | ✅ 클래스만 | **✅ 메서드 + 인자 포함** |
| 예외(throws) | ✅ 포함 | ❌ 미지원 | **✅ 지원** |
| 캐싱 | - | ❌ 없음 | **✅ .applycrypto/cache/** |
| 시트 개수 | 4개 | 6개 (표제부, Object정의, Object선언, login, 기타, 변경) | 동일 |
| 출력 모드 | 클래스별 개별 또는 ZIP | 동일 구현 | 동일 |
| Javadoc 처리 | HTML 제거, 텍스트 추출 | 구현됨 | 구현됨 |
| 예외 처리 | 파싱 실패 시 경고 후 계속 | 구현됨 |

### J-2. 주요 개선 사항 (v2.3 이상)

**문제 해결**:
1. ✅ **메서드 중복 제거**: 정규식 기반 중괄호 추적의 오류 → AST 파싱으로 정확한 추출
2. ✅ **메서드 메타정보 부족**: 파라미터/어노테이션 텍스트 형식 → 구조화된 객체로 확장
3. ✅ **Private 메서드 누락**: 필터링으로 제외 → 모든 접근제한자 포함
4. ✅ **메서드 Sheet 메타정보 표시**: 간단한 정보만 → 어노테이션, 수식어, 파라미터 자동 표시
5. ✅ **성능**: 캐싱 미지원 → CacheManager 활용으로 재파싱 회피

**Technical Stack 변경**:
- **Before**: `re` (정규식) + 텍스트 기반 처리
- **After**: `JavaASTParser` (tree-sitter-java) + `CacheManager` (AST 기반)

### J-3. 현재 상태 (v2.3+ 최신)

✅ **완료된 개선사항**:
1. ✅ JavaASTParser(tree-sitter) 기반 메서드 추출 - 중복 제거, 정확도 향상
2. ✅ 메서드 메타정보 확장 - 파라미터, 어노테이션, 예외, 수식어 자동 추출
3. ✅ 메서드 시그니처 자동 생성 - `methodName(param1, param2)` 형식
4. ✅ 모든 접근제한자 처리 - public, protected, private 메서드 포함
5. ✅ 캐싱 지원 - 반복 실행 성능 향상 (.applycrypto/cache/)
6. ✅ **Input Parameter 행 추가** (Row 6/13) - 파라미터 시그니처 자동 표시
7. ✅ **Return Type Generic 타입 보존** - `List<Employee>`, `Map<String, Object>` 등 '<>' 문자 유지
8. ✅ **LLM 기반 메서드 요약** (Row 9 참고사항) - `--llm` 옵션으로 8-점 아키텍처 분석 (한줄요약, 핵심목적, 처리흐름, 조건분기, 반복처리, 비즈니스로직, 외부의존성, 성능특성)
9. ✅ **LLM 응답 파싱 강화** - 마크다운 코드블럭 자동 제거 (````json`, ` ``` ` 처리), JSON 파싱 오류 명시적 처리, 빈 응답 감지 및 "기능 없음" 반환, 휴리스틱 폴백 제거
10. ✅ **참고사항 행 포맷팅** - 테두리 적용, 줄바꿈 활성화, 높이 자동 조절

🔄 **향후 검토 개선사항**:
1. 필드 추출 기능 강화 (현재는 메서드 중심)
2. `--input-json` 옵션 구현으로 CLI 유연성 향상
3. 어노테이션 value 추출 심화 (예: `@RequestMapping("/user")` 에서 URL 값 분석)
4. 메서드 복잡도 분석 (순환 복잡도, LOC 등) 추가
5. 상속 계층 분석 (superclass 메서드 병합 처리 등)

## K. 실행 예시

### K-1. 기본 실행

```bash
python main.py generate-spec --config config.json
```

**동작**:
1. config.json 읽음
2. target_project 경로의 ChangedFileList_*.txt 조회
3. 각 Java 파일 처리
4. 클래스별 Excel 파일 생성 in `{target_project}/.applycrypto/artifacts/`

### K-2. ZIP 출력

```bash
python main.py generate-spec --config config.json --zip
```

**동작**: 
1. 위와 동일한 처리
2. 마지막에 모든 Excel 파일을 `{ProjectName}_specs_{YYYYMMDD}.zip`로 압축
3. 개별 Excel 파일 생성 생략 (ZIP 내에만 포함)

## L. 함수 레퍼런스

### L-1. 진입점

```python
def generate_spec(config: Configuration, zip_output=False):
    """Java 클래스들로부터 Excel 사양서를 생성합니다."""
```

### L-2. 파서 함수 (JavaASTParser 기반)

```python
# JavaASTParser 초기화 및 파싱
java_parser = JavaASTParser(cache_manager=cache_manager)
tree, error = java_parser.parse_file(file_path)
classes = java_parser.extract_class_info(tree, file_path)

# 메서드 메타정보 변환
def _convert_method_objects_to_dict(methods, source) -> list:
    """JavaASTParser Method 객체를 사전 형식으로 변환
    
    반환:
    [
      {
        'name': 메서드명,
        'return_type': 반환타입,
        'param_signature': 'param1, param2',
        'parameters': [{'name': 'user', 'type': 'User'}],
        'annotations': ['@RequestMapping', '@ResponseBody'],
        'exceptions': ['IOException'],
        'modifiers': ['static', 'final'],
        'access_modifier': 'public',
        'source': 메서드본문,
        'comment': Javadoc
      },
      ...
    ]
    """

# 하위 호환성: 정규식 기반 함수 (DEPRECATED)
def extract_methods(source) -> list:
    """정규식 기반 메서드 추출 (현재는 JavaASTParser 권장)"""

# 유틸리티 함수
def read_java_file(file_path) -> str:
    """Java 파일을 다양한 인코딩으로 안전하게 읽음"""

def extract_package(source) -> str:
    """소스에서 package 선언 추출"""

def extract_imports(source) -> list:
    """소스에서 모든 import 추출"""

def extract_method_body(source, brace_start) -> str:
    """메서드 본문 추출 (중괄호 매칭, 들여쓰기 정규화)"""

def extract_method_with_annotations(source, method_name) -> str:
    """메서드 어노테이션 + 선언 + 본문 추출"""

def extract_comment_before_method(source, method_start) -> str:
    """메서드 직전 주석/Javadoc 추출"""
```

### L-3. 워크북 생성 함수

```python
def create_specification_workbook_from_scratch(first_changed_path) -> Workbook:
    """6개 시트로 구성된 빈 워크북 생성"""

def create_cover_sheet(wb) -> None:
    """표제부 시트 생성"""

def create_object_definition_sheet(wb) -> None:
    """Object정의 시트 생성"""

def create_object_declaration_sheet(wb) -> None:
    """Object선언 시트 생성"""

def create_method_template_sheet(wb) -> None:
    """login (Method Template) 시트 생성"""

def create_other_definitions_sheet(wb) -> None:
    """기타정의사항 시트 생성"""

def create_change_history_sheet(wb) -> None:
    """변경이력 시트 생성"""
```

### L-4. 시트 채우기 함수

```python
def fill_cover_sheet(ws, class_name, file_path, source, package, first_changed_path):
    """표제부 시트에 클래스 메타정보 채우기"""

def fill_object_definition_sheet(ws, methods, file_path):
    """Object정의 시트에 메서드 목록 채우기"""

def fill_object_declaration_sheet(ws, package, imports, annotations, extends, implements, source):
    """Object선언 시트에 클래스 선언 정보 채우기"""

def create_method_sheet(wb, method, source, template_ws) -> None:
    """메서드별 동적 시트 생성"""
```

### L-5. 유틸리티 함수

```python
def _extract_project_name(path_str) -> str:
    """파일 경로에서 프로젝트명 추출"""

def _sanitize_sheet_title(t, existing_titles) -> str:
    """엑셀 시트명 안전성 검증 (31자 제한, 금지 문자 제거)"""

def _get_class_body(source, class_name) -> str:
    """지정한 클래스의 본문(중괄호 범위) 반환"""

def read_changedFileList_excel(target_project) -> tuple:
    """target_project의 ChangedFileList_*.txt 읽음 → (파일_경로_리스트, 첫_변경_정보_맵)"""
```

---

---

**문서 작성일**: 2025년 2월 3일  
**버전**: 2.3+ (JavaASTParser 통합 - AST 기반)  
**상태**: spec_generator.py v2.3+ 호환 (프로덕션 운영 중)

## I. Implementation notes (실제 구현 특이사항):

### 입력 및 진입점
- **진입점**: `generate_spec(config: Configuration, zip_output=False, diff_mode=False)`
- **입력 방식**: `{target_project}/ChangedFileList_*.txt` 에서 Java 파일 경로 읽음
- **CLI 옵션**: 
  - `--zip`: ZIP 출력 활성화
  - `--diff`: 변경된 메소드만 포함 (config.artifact_generation.old_code_path 필수)
- JSON 기반 입력 필요시 외부에서 별도 처리

### 파서 및 캐싱
- **파서**: JavaASTParser (tree-sitter-java 기반) - AST 정확도 우선
- **캐싱**: CacheManager를 사용하여 파싱 결과를 `{target_project}/.applycrypto/cache/` 에 저장
- **성능**: 반복 실행 시 캐시 활용으로 재파싱 불필요 → 성능 향상
- **한계**: 매우 복잡한 Java 문법(레코드, 람다, 모듈 시스템)의 경우 전처리 고려

### --diff 옵션 (변경된 메소드만 포함)

#### 기능 개요
변경 전/후 코드를 비교하여 **변경된 파일의 메소드만 포함**하는 사양서를 생성합니다.

#### 사용 방법
```bash
# 기본: 모든 메소드
python main.py generate-spec --config config.json

# 변경된 메소드만
python main.py generate-spec --config config.json --diff

# ZIP 압축 + 변경만
python main.py generate-spec --config config.json --zip --diff
```

#### 필수 설정
`config.json`에 다음이 포함되어야 함:
```json
{
  "artifact_generation": {
    "old_code_path": "변경 전 프로젝트 경로"
  }
}
```

#### 동작 방식
1. **파일 필터링** (`_get_changed_java_files_flexible()`)
   - `target_project`와 `old_code_path` 비교
   - MD5 해시 기반 파일 내용 비교
   - 경로 구조 자동 감지 (src/main/java, src/com/mybatis 등 모두 지원)
   - 변경된 파일 목록 추출

2. **ChangedFileList 교집합**
   - ChangedFileList의 파일 중에서 실제로 변경된 파일만 선별
   - 일관성 유지: 기본 모드와 동일한 파일 수 처리

3. **메소드 필터링** (`extract_changed_methods()`)
   - 변경 파일의 메소드부터 변경 메소드 추출
   - "ClassName.methodName" 형식의 변경된 메소드 목록 반환

4. **시트 생성**
   - 변경된 메소드만 Excel 시트에 포함
   - 변경 메소드 없는 파일은 스킵

#### 기술 특징
- **경로 유연성**: 프로젝트 구조 자동 감지 (src 이후 경로로 정규화)
- **정확한 비교**: MD5 해시로 바이너리 레벨 비교
- **새 파일 감지**: 추가된 파일도 변경 파일로 인식
- **예외 처리**: 파일 읽기 실패 시 변경된 것으로 간주

#### 예제

**결과 비교**:
```
기본 모드 (--diff 없음):
  Employee: 15개 메소드 (전체)
  BookController: 14개 메소드 (전체)
  EmpController: 17개 메소드 (전체)
  → 총 65개 메소드

--diff 모드:
  Employee: 4개 메소드 (변경된 것만)
  BookController: 1개 메소드 (변경된 것만)
  EmpController: 11개 메소드 (변경된 것만)
  → 총 47개 메소드 (27% 감소)
```

**이점**:
- 변경사항에만 집중
- 산출물 크기 축소
- 리뷰 효율성 증대

### 메서드 정보 추출 (v2.3)
- **범위**: public, protected, **private** 모두 포함 (접근제한자 필터 없음)
- **메타정보**: 파라미터, 어노테이션, 예외(throws), 수식어(static/final/abstract) 자동 추출
- **메서드 시트**: 각 메서드별 동적 시트 생성, 메타정보 자동 채우기
- **어노테이션**: 메서드 레벨 어노테이션 추출 및 "설계자 상세 Logic" 셀에 표시

### 출력
- **경로**: `{target_project}/.applycrypto/artifacts/`
- **개별 모드**: `{ClassName}_spec.xlsx` (클래스당 1개)

## K. LLM 기반 메서드 요약 (v2.3+)

### K-1. 개요

**목적**: 메서드의 기능을 자연어로 요약하여 Excel 사양서의 Row 9 (참고사항) 에 자동 기입

**필수 Import**:
```python
import json  # LLM 응답 JSON 파싱용
```

### K-2. 함수 설명

**함수**: `generate_method_summary(method_source, method_name, llm_provider)`

**파라미터**:
- `method_source` (str): 메서드 전체 소스 코드 (어노테이션 포함)
- `method_name` (str): 메서드명
- `llm_provider` (LLMProvider or None): LLM 프로바이더 객체

**반환값**: 한글 자연어 요약 (250자 이내)

**동작 로직**:
1. **LLM 모드** (llm_provider 제공 시):
   - Prompt 작성: 메서드 소스 + 분석 규칙 (암호화/보안 우선)
   - LLM 호출 → JSON 응답 파싱: `response = json.loads(llm_response)`
   - 로그: `[메서드 요약 LLM] {method_name}: {summary}`
   - 성공 시 LLM 요약 반환

2. **예외 처리** (JSON 파싱 실패, LLM 초기화 실패 등):
   - 자동으로 휴리스틱 모드로 폴백 (no fallthrough 불가)

3. **휴리스틱 모드** (llm_provider=None 또는 LLM 예외):
   - Step 1: JavaDoc/코멘트 추출 → `extract_javadoc_and_comments(method_source)`
   - Step 2: 코멘트 기반 요약 → `generate_method_summary_from_comments(javadoc, comments)`
   - Step 3: 코드 패턴 인식 (우선순위)
     * 암호화/복호화: `decrypt`, `encrypt`, `CryptoService` 키워드
     * 데이터 접근: `repository`, `mapper`, `findAll`, `query` 키워드
     * 작업 감지: `save`, `update`, `delete` (void 메서드)
   - Step 4: 제네릭 처리 (fallback)
   - 로그: `[메서드 요약 주석]` (Step 2) 또는 `[메서드 요약 휴리]` (Step 3 이후)

### K-3. 활성화

**CLI 옵션**:
```powershell
# LLM 활성화
python main.py generate-spec --config config.json --llm

# 변경된 파일만 + LLM
python main.py generate-spec --config config.json --diff --llm
```

**필수 설정** (config.json):
```json
{
  "llm_provider": "watsonx_ai"  # 또는 "anthropic" 등
}
```

**API KEY** (환경변수):
```powershell
# WatsonX.AI (권장)
$env:WATSONX_API_KEY = "your-api-key"
$env:WATSONX_PROJECT_ID = "your-project-id"

# Claude (옵션)
$env:ANTHROPIC_API_KEY = "your-api-key"
```

### K-4. 예시

**Input**:
```java
@RequestMapping("/login")
@ResponseBody
public String login(User user, String password) throws IOException {
    UserDTO dto = employeeService.login(user);
    if (dto != null) {
        return "200";
    } else {
        return "500";
    }
}
```

**LLM 출력** (API KEY 설정 시):
```
[메서드 요약 LLM] login: 사용자 로그인 인증을 수행하고, 성공 여부에 따라 HTTP 상태코드를 반환합니다.
```

**휴리스틱 출력** (API KEY 미설정):
```
[메서드 요약 주석] login: (JavaDoc 있으면 추출)
또는
[메서드 요약 휴리] login: 데이터베이스 조회 후 인증 결과에 따라 상태 응답을 반생합니다.
```
- **ZIP 모드**: `{ProjectName}_specs_{YYYYMMDD}.zip` (전체 통합)
- **형식**: Excel 2007+ (.xlsx) 호환

