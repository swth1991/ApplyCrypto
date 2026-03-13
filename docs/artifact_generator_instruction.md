# 🗂️ 변경내역(Artifact) 생성 구현 명세서

이 문서는 `src/generator/artifact_generator.py`가 따라야 할 **구현 명세서(Implementation Specification)** 입니다.  
작성일: 2026-02-03 | 최종 검토: 코드 기반 분석

---

## A. 목적

**핵심**: 변경된 파일 목록(`ChangedFileList_*.txt`)을 입력으로 받아, 도메인별 이관 산출물 Excel 통합 워크북을 생성합니다.  
생성되는 Excel에는 업무 요건, 개발 문서, 통신 인터페이스, DB/Privacy, 테스트 케이스, 소스 코드 변경 내역 등이 포함됩니다.

---

## B. 입력 및 전제조건

### B-1. 입력 방식
- **입력 파일**: `ChangedFileList_*.txt` (프로젝트 루트의 `.applycrypto/` 디렉터리 내)
- **파일 포맷**: 한 줄에 하나의 파일 경로 (상대경로 또는 절대경로)
- **인코딩**: UTF-8
- **파일 패턴 매칭**: glob 패턴 `{target_project}/.applycrypto/ChangedFileList_*.txt`로 첫 번째 일치 파일 사용

### B-2. 선행 조건
1. `config.json`에 다음 필드 필수:
   - `target_project`: 변경된 프로젝트의 경로
   - `artifact_generation.old_code_path`: 원본 코드(변경 전 백업) 경로 (비교 대상)
2. 타겟 프로젝트와 원본 백업 경로 모두 존재해야 함
3. 원본 백업 경로의 파일 구조가 타겟 프로젝트와 동일해야 diff 생성 가능

### B-3. 선택 사항
- **LLM 옵션**: `use_llm=True` 시 개발 관련 문서 고도화 (자동 요약 생성)
  - LLM 설정: `config.json`의 `llm_provider` 필드 참조

---

## C. 출력물 구조

### C-1. 출력 위치
- **기본 경로**: `{target_project}/.applycrypto/artifacts/`
- **파일명 형식**: `{프로젝트명} 이관 산출물 - {YYYYMMDD}.xlsx`
  - 예: `book-ssm 이관 산출물 - 20260203.xlsx`

<<<<<<< HEAD
### C-2. 통합 워크북 구조 (6개 시트)
모든 변경 파일의 정보를 **프로젝트 단위로 하나의 Excel 워크북**에 통합합니다.

Implementation notes (실제 구현 특이사항):

- 코드(`src/generator/artifact_generator.py`)는 `config.artifact_generation.old_code_path`가 반드시 설정되어 있어야 합니다; 없으면 예외를 발생시킵니다.
- 입력 파일은 `{target_project}/.applycrypto/ChangedFileList_*.txt` 패턴으로 검색하며, 존재하지 않으면 `FileNotFoundError`가 발생합니다.
- 출력 파일명 패턴: `{target_project}/applycrypto/artifacts/{projectName} 이관 산출물 - {YYYYMMDD}.xlsx` (코드 내 생성 규칙).
- 옵션: LLM 보강은 함수 파라미터 `use_llm`(boolean)로 제어됩니다.

## D. 항목별 규격 (엑셀 컬럼)

| 순서 | 시트명 | 설명 |
|-----|--------|------|
| 0 | **0.업무요건** | 변경 대상 클래스/파일의 업무 배경 및 요구사항 (현재 템플릿 시트) |
| 1 | **1.개발관련문서** | 변경 클래스별 개발 사항, 주요 로직 변경, 메서드 상세 정보 및 논리적 변경 블록 분석 결과 |
| 2 | **2.통신인터페이스추가및변경여부** | API 엔드포인트 변경 현황 (@RequestMapping, @GetMapping 등 추출) |
| 3 | **3.DB_파일_로그변경 여부 및 개인정보 여부** | DB/파일/로그 관련 변경 및 민감도 분류 |
| 5 | **5.테스트케이스** | 변경 영향도 및 테스트 케이스 현황 (현재 템플릿 시트) |
| 6 | **6.소스코드** | 변경 파일의 구체적인 코드 변경 내역 (Before/After 비교) |

> **참고**: 시트 번호 4번은 건너뜁니다 (구현체 로직 유지).

---

## D. 항목별 상세 규격 (엑셀 컬럼 및 구조)

### D-1. 업무요건 시트 (Sheet: `0.업무요건`)

현재 **템플릿 시트**로 운영됨. 사용자가 수동 입력하는 영역.

| 항목 | 형식 | 설명 |
|-----|------|------|
| 시스템명 | 텍스트 | - |
| 요청자 | 텍스트 | - |
| 업무내용 | 텍스트 (Wrap) | - |
| 변경범위 | 텍스트 (Wrap) | - |

### D-2. 개발관련문서 시트 (Sheet: `1.개발관련문서`)

**클래스별** 개발 정보를 행 단위로 기록합니다.

| 컬럼 | 항목명 | 설명 | 예시 |
|-----|--------|------|------|
| A | **파일명** | 변경된 Java 파일명 | `UserController.java` |
| B | **클래스명** | 파일 내 최상위 public 클래스명 | `UserController` |
| C | **패키지명** | 클래스 패키지명 (source file의 package 선언에서 추출) | `com.example.controller` |
| D | **파일경로** | 프로젝트 내 상대경로 (정규화됨, `os.path.normpath`) | `src/main/java/com/example/controller/UserController.java` |
| E | **변경유형** | 파일 상태 유형 | `ADD`, `MODIFY`, `DELETE` |
| F | **변경메서드수** | 변경된 메서드 개수 (라인 diff에서 메서드 단위 추출) | `3` |
| G | **주요변경내용** | 메서드별 간단 요약 (wrap_text=True) | `getUserInfo 메서드 로직 변경; addUser 메서드 예외처리 추가` |
| H | **API_엔드포인트** | 변경된 API 엔드포인트 (@RequestMapping 등 추출) | `POST /users`, `GET /users/{id}` |
| I | **영향테이블** | 접근하는 DB 테이블 목록 | `user_account, user_profile` |
| J | **LLM분석결과** | (LLM 활성화 시만) 자동 생성된 요약 | - |

### D-3. 통신인터페이스추가및변경여부 시트 (Sheet: `2.통신인터페이스추가및변경여부`)

**API 엔드포인트** 변경 내역을 행 단위로 기록합니다.

| 컬럼 | 항목명 | 설명 |
|-----|--------|------|
| A | **파일명** | API가 정의된 파일명 |
| B | **클래스명** | 엔드포인트 클래스명 |
| C | **엔드포인트** | HTTP 메서드 + 경로 (정규식 추출) |
| D | **메서드명** | 엔드포인트를 처리하는 메서드명 |
| E | **HTTP메서드** | `GET`, `POST`, `PUT`, `DELETE` 등 |
| F | **경로** | `/users`, `/users/{id}` 등 |
| G | **변경유형** | `신규`, `변경`, `삭제` |
| H | **요청/응답구조** | 간단 설명 (wrap) |

**추출 방식**: 정규식으로 `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping` 등의 어노테이션 파싱

### D-4. DB_Privacy 시트 (Sheet: `3.DB_Privacy`)

**DB 접근** 및 **개인정보** 관련 변경 내역.

| 컬럼 | 항목명 | 설명 |
|-----|--------|------|
| A | **파일명** | 파일명 |
| B | **클래스명** | 클래스명 |
| C | **메서드명** | DB를 접근하는 메서드명 |
| D | **접근테이블** | 쿼리/Repository에서 접근하는 테이블명 |
| E | **개인정보항목** | 민감 컬럼 (예: 주민번호, 휴대폰번호, 이메일) |
| F | **변경사항** | DB 구조 또는 Privacy 정책 변경 내용 (wrap) |
| G | **영향도** | `높음`, `중간`, `낮음` |

### D-5. 테스트케이스 시트 (Sheet: `4.테스트케이스`)

현재 **템플릿 시트**로 운영됨. 사용자가 수동 입력하는 영역.

| 항목 | 형식 |
|-----|------|
| 테스트명 | 텍스트 |
| 테스트케이스 | 텍스트 (Wrap) |
| 예상결과 | 텍스트 (Wrap) |

### D-6. 소스코드 시트 (Sheet: `6.소스코드`)

**파일별** 코드 변경 내역 (Before/After 비교).

| 컬럼 | 항목명 | 설명 |
|-----|--------|------|
| A | **파일명** | 변경된 파일 |
| B | **클래스명** | 파일 내 클래스 |
| C | **메서드명** | 변경이 발생한 메서드명 |
| D | **변경라인** | 시작라인-종료라인 (예: `120-145`) |
| E | **변경유형** | `추가`, `변경`, `삭제` |
| F | **변경 전 코드** | Before 스니펫 (최대 15줄, wrap_text=True) |
| G | **변경 후 코드** | After 스니펫 (최대 15줄, wrap_text=True) |
| H | **변경사유** | 간단 설명 (wrap) |

**diff 생성 방식**:
1. 원본(old_code_path) 파일과 타겟 파일을 `difflib.unified_diff()` 또는 `difflib.SequenceMatcher`로 비교
2. 메서드 단위로 변경 블록 추출 (`extract_logical_change_blocks()` 함수 사용)
3. 각 변경 블록에 대해 Before/After 스니펫을 셀에 기록

---

## E. 처리 규칙 및 로직

### E-1. 입력 파일 처리

```
1. ChangedFileList_*.txt 파일을 glob 패턴으로 검색
   - {target_project}/.applycrypto/ChangedFileList_*.txt
   
2. 첫 번째 매칭 파일을 선택 (최신 파일 기준)
   
3. 파일을 행 단위로 읽고, 각 행을 상대경로로 정규화
   - os.path.normpath() 적용
   - 경로는 target_project 기준의 상대경로로 변환
   
4. 파일 목록을 딕셔너리 리스트로 반환
   ```python
   files = [
       {'file_path': 'src/main/java/com/example/UserController.java', 'project_root': '...'},
       ...
   ]
   ```
```

### E-2. 파일 분석 및 메타 추출

각 파일에 대해 다음 정보를 추출합니다:

| 항목 | 추출 방식 | 예시 |
|-----|---------|------|
| **패키지명** | Java source의 `package` 선언문 (정규식) | `com.example.controller` |
| **클래스명** | `public class {클래스명}` 패턴 (정규식) | `UserController` |
| **메서드명** | `public|private|protected ... {메서드명}(` 패턴 | `getUserInfo`, `addUser` |
| **주석** | Javadoc 또는 블록 주석 (첫 문단만) | - |
| **API 엔드포인트** | `@RequestMapping`, `@GetMapping` 등 어노테이션 추출 | `GET /users/{id}` |

**정규식 예시**:
- 패키지: `^\\s*package\\s+([\\w.]+);`
- 클래스: `public\\s+class\\s+(\\w+)`
- 메서드: `(public|private|protected)?\\s*\\w+\\s+(\\w+)\\s*\\(`
- API: `@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)\\s*\\([^)]*\\)`

### E-3. Diff 생성 및 변경 블록 추출

```python
# 원본과 타겟 파일 비교
with open(old_file) as f:
    original_lines = f.readlines()
with open(new_file) as f:
    modified_lines = f.readlines()

# difflib를 이용한 비교
differ = difflib.Differ()
diff_result = list(differ.compare(original_lines, modified_lines))

# 논리적 변경 블록 추출 (메서드/구조화된 영역 단위)
blocks = extract_logical_change_blocks(original_lines, modified_lines)
```

### E-4. 논리적 변경 블록 추출 (`extract_logical_change_blocks()`)

메서드를 기준으로 변경 범위를 그룹화합니다:

1. **메서드 시작 라인 탐지**: 원본 파일에서 모든 메서드의 시작 라인 추출
2. **diff 결과 맵핑**: 각 변경된 라인을 메서드에 할당
3. **블록 생성**: 각 메서드별로 변경 전/후 코드 스니펫 생성
4. **요약 작성**: 변경 내용을 간단한 텍스트로 설명

**블록 구조**:
```python
block = {
    'file_path': '...',
    'class_name': '...',
    'method_name': '...',
    'start_line': 120,
    'end_line': 145,
    'change_type': 'MODIFY',
    'original_snippet': [...],  # 변경 전 코드
    'modified_snippet': [...],  # 변경 후 코드
    'summary': '...'             # 변경 요약
}
```

### E-5. 특수 시트 처리

#### (1) API 엔드포인트 추출

- 소스 파일에서 `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping` 어노테이션 검색
- 각 어노테이션의 `value` 또는 path 인자 추출
- HTTP 메서드는 어노테이션 종류에서 유추

```python
def extract_api_endpoints_with_method(file_path: str) -> List[Dict]:
    """
    반환: [
        {'endpoint': 'GET /users', 'method': 'getUserList', 'annotation': '@GetMapping("/users")'},
        ...
    ]
    """
```

#### (2) DB 테이블/Privacy 정보

- 메서드 내부에서 Repository/Mapper 호출 탐지
- 호출된 메서드명에서 테이블 이름 추론 (예: `UserRepository.findByUserId()` → `user` 테이블)
- Privacy 키워드 탐지: `ssn`, `주민번호`, `password`, `암호`, `phone`, `이메일` 등

#### (3) LLM 기반 고도화 (선택사항, `use_llm=True` 시)

- 각 메서드의 변경 전/후 코드 스니펫을 LLM에 전달
- LLM이 변경 사유를 자동 생성
- 결과를 `개발관련문서` 시트의 'LLM분석결과' 컬럼에 기록

### E-6. 워크북 조합 및 저장

```python
1. 템플릿 시트 생성
   - 업무요건, 테스트케이스 (사용자 입력용 빈 시트)

2. 동적 시트 생성
   - 개발관련문서, 통신인터페이스, DB_Privacy, 소스코드, 소스코드_논리적변경블록
   - ChangedFileList의 각 파일에 대해 데이터 행 추가

3. 수식 제거
   - openpyxl의 수식을 제거하여 순수 값만 저장 (remove_all_formulas 함수)

4. 파일 저장
   - wb.save({output_path})
```

---

## F. 포맷/스타일 가이드

### F-1. 헤더 스타일
- **폰트**: 맑은 고딕, 10pt, **굵게(bold)**
- **배경색**: `#DFDFDF` (밝은 회색)
- **정렬**: 가운데 정렬, 세로 중앙

### F-2. 데이터 셀 스타일
- **폰트**: 맑은 고딕, 10pt, 일반체
- **테두리**: 모든 셀에 적용 (얇은 선)
- **정렬**:
  - 일반 텍스트 (파일명, 클래스명): 왼쪽 정렬
  - 변경유형, 변경라인: 가운데 정렬
  - 긴 텍스트 (설명, 요약, 코드): **Wrap text 활성화** + 왼쪽 정렬 + 위쪽 정렬

### F-3. 행 높이
- **헤더 행**: 높이 18
- **데이터 행**: 기본 높이 16, wrap 적용 시 자동 조정

### F-4. 컬럼 너비
| 컬럼명 | 권장 너비 |
|-------|---------|
| 파일명 | 30 |
| 클래스명 | 25 |
| 메서드명 | 25 |
| 변경라인 | 15 |
| 코드 스니펫 | 60 |
| 설명/요약 | 50 |

### F-5. 날짜 형식
- 생성 일시: `YYYY-MM-DD HH:MM:SS` (문자열)

---

## G. 예외 처리 및 오류 처리

### G-1. 파일 읽기 오류
```
파일을 읽을 수 없는 경우 (인코딩 오류, 권한 없음, 파일 없음):
→ try-except로 감싸고 warn 메시지 출력
→ 해당 파일 생략하고 다음 파일로 진행 (즉, 전체 프로세스 중단 안 함)
```

### G-2. diff 생성 실패
```
원본 파일이 없거나 diff를 생성할 수 없는 경우:
→ 파일 메타 정보만 기록 (코드 스니펫 없이)
→ '변경사유' 컬럼에 "원본 파일 미제공" 기록
```

### G-3. 메타 추출 실패 (정규식 패턴 미매칭)
```
패키지명/클래스명/메서드명을 추출하지 못한 경우:
→ 해당 필드는 빈 문자열로 처리
→ 해당 파일은 여전히 워크북에 기록되지만 메타 정보는 부분 누락
```

---

## H. 검증 및 테스트

### H-1. 단위 테스트
- `read_changedFileList()`: 파일 목록 읽기 정확성
- `extract_logical_change_blocks()`: diff 블록 추출 정확성
- `extract_api_endpoints_with_method()`: API 엔드포인트 추출 정확성
- 정규식 패턴: 패키지, 클래스, 메서드명 추출 정확성

### H-2. 통합 테스트
- 소규모 프로젝트 (3~5 클래스) 로 전체 파이프라인 검증
- 워크북 생성 및 파일 저장 성공 여부
- 모든 시트의 데이터 일관성
- 스타일(헤더, wrap, 정렬) 적용 확인

### H-3. 오류 시뮬레이션
- 파일 읽기 오류: ChangedFileList에서 존재하지 않는 파일 포함
- 인코딩 오류: 비 UTF-8 파일
- 메타 추출 실패: 비표준 Java 구문

---

## I. 예외 및 제한사항

### I-1. 파일 형식 제한
- **지원 언어**: Java only (현재)
- **지원하지 않는 파일**: 바이너리 파일 (이미지, 실행 파일 등)
- **JSON 입력**: 명세서 초안에서 언급되었으나 현재 구현에서는 TXT only

### I-2. 메타 추출 한계
- **Complex Java 문법**: 복잡한 제네릭, 람다식, nested classes 등의 정규식 파싱 한계
  - 권장: Java AST 파서(ANTLR, Grapa-v3 등)로 마이그레이션 고려
- **주석 처리**: Javadoc 외 인라인 주석의 완전 파싱 어려움
- **쿼리 ID 추출**: Repository/Mapper 호출에서 SQL ID를 정확히 추출하기 어려움

### I-3. 성능 고려사항
- 대규모 프로젝트 (1000+ 파일): 메모리 및 처리 시간 증가 예상
- LLM 사용 시: API 호출 시간으로 인한 추가 지연

### I-4. 미구현 항목 (초안 대비)
- `--out-dir`: CLI에서 출력 경로 지정 미지원 (고정 경로 사용)
- `--zip`: 개별 ZIP 생성 미지원
- `--controller-only`: Controller 파일만 선택 미지원
- `--dry-run`: 실행 시뮬레이션 미지원

---

## J. 주요 함수 목록

| 함수명 | 용도 | 입력 | 출력 |
|--------|------|------|------|
| `generate_artifact(config, use_llm)` | 메인 진입점 | Configuration 객체 | Excel 파일 생성 |
| `read_changedFileList(file, project_name)` | 파일 목록 읽기 | TXT 파일 경로 | Dict 리스트 |
| `extract_logical_change_blocks(old_lines, new_lines)` | diff 블록 추출 | 코드 라인 배열 | 변경 블록 리스트 |
| `extract_api_endpoints_with_method(file_path)` | API 엔드포인트 추출 | Java 파일 경로 | Dict 리스트 (endpoint, method) |
| `fill_development_docs(wb, file_info, ...)` | 개발 문서 시트 채우기 | Workbook, 파일 정보 | Workbook (수정됨) |
| `fill_source_code(wb, file_info, ...)` | 소스 코드 시트 채우기 | Workbook, 파일 정보 | Workbook (수정됨) |
| `remove_all_formulas(wb)` | 워크북 수식 제거 | Workbook | Workbook (수정됨) |

---

## K. 참고: 명세서와 실제 구현의 주요 차이점

| 항목 | 초안 명세서 | 실제 구현 | 비고 |
|-----|-----------|---------|------|
| **시트 개수** | 3개 (요약, 상세, 패치) | **6개** (0, 1, 2, 3, 5, 6) | 도메인별 분류로 확대됨 (4번은 공백 예약) |
| **입력 형식** | TXT, JSON | **TXT only** | JSON 지원 미구현 |
| **출력 형식** | 클래스별 개별 파일 | **프로젝트 단위 통합 파일** | 한 개의 xlsx로 통합 |
| **CLI 옵션** | --out-dir, --zip, --controller-only, --dry-run | 미지원 (고정 경로 사용) | 향후 추가 예정 |
| **LLM 옵션** | 미언급 | `use_llm=True` 지원 | 개발 문서 고도화 |
| **메타 추출** | AST 기반 파싱 | **AST + 정규식 혼합** | 성능 및 정확도 고려 |

