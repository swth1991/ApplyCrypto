# 🛠️ AS-IS 분석서 통합 구현 명세서

이 문서는 `src/generator/analysis_report_generator.py`가 따라야 할 구현 명세서(Implementation Specification)입니다. 실제 코드 분석을 통해 정확한 기능, 데이터 흐름, 출력 구조를 명시합니다.

---

## A. 목적 및 개요

**핵심 기능**: 대상 프로젝트의 `.applycrypto/three_step_results` 디렉터리에 저장된 분석 JSON 파일들(step1_query_analysis.json, step2_planning.json, table_access_info.json)을 읽어서, 암호화 대상 테이블 및 쿼리의 AS-IS 분석서를 Excel 형식으로 생성합니다.

**산출물**: `{target_project}/.applycrypto/artifacts/AsIs_Analysis_Report_{TYPE}_{YYYYMMDD}.xlsx`
- TYPE: 분석 유형 (ThreeStep 또는 TypeHandler)

**분석 유형 (modification_type)**:
1. **ThreeStep**: step1_query_analysis.json + step2_planning.json + table_access_info.json을 결합 사용
2. **TypeHandler** (또는 TypeHandler): step1_query_analysis.json + table_access_info.json만 사용 (step2 미사용)

---

## B. 입력 및 전제조건

### B-1. 입력 데이터 경로

```
{target_project}
├── .applycrypto/
│   ├── three_step_results/
│   │   └── [일시]/
│   │       └── [테이블명]/
│   │           └── [컨트롤러명]/
│   │               ├── step1_query_analysis.json
│   │               └── step2_planning.json (ThreeStep만)
│   └── results/
│       └── table_access_info.json
```

### B-2. 필수 파일 및 데이터 구조

#### B-2.1 step1_query_analysis.json (필수)

```json
{
  "metadata": {
    "table_name": "테이블명",
    "file_paths": [...]
  },
  "result": {
    "queries": [
      {
        "query_id": "쿼리ID",
        "sql_summary": "SQL 요약",
        "input_mapping": {
          "crypto_fields": [
            {"column_name": "col1"},
            ...
          ]
        },
        "output_mapping": {
          "crypto_fields": [
            {"column_name": "col2"},
            ...
          ]
        }
      }
    ]
  }
}
```

#### B-2.2 step2_planning.json (ThreeStep만 필수)

```json
{
  "metadata": {
    "table_name": "테이블명",
    "file_paths": [...]
  },
  "result": {
    "data_flow_analysis": {
      "flows": [
        {
          "flow_id": "flow1",
          "sql_query_id": "쿼리ID"
        }
      ]
    },
    "modification_instructions": [
      {
        "flow_id": "flow1",
        "file_name": "ClassName.java",
        "target_method": "메서드명",
        "action": "action_type",
        "reason": "변경 사유",
        "insertion_point": "위치",
        "code_pattern_hint": "힌트"
      }
    ]
  }
}
```

#### B-2.3 table_access_info.json (필수)

```json
{
  "table_name": "테이블명",
  "columns": [
    {
      "name": "컬럼명"
    }
  ],
  "sql_queries": [
    {
      "id": "쿼리ID",
      "strategy_specific": {
        "result_map": "true/false/null",
        "result_field_mappings": [
          ["mapping1"],
          ["mapping2"]
        ]
      }
    }
  ]
}
```

### B-3. 실행 환경

- Python 3.x
- openpyxl (Excel 파일 생성)
- config.json 설정:
  - `target_project`: 대상 프로젝트 경로 (필수)
  - `modification_type`: 분석 유형 (필수, "ThreeStep" 또는 "TypeHandler")

---

## C. 출력물 구조

### C-1. Excel 워크북 구성

2개 시트로 구성:

1. **개요** (분석 항목 정의/설명)
2. **대상목록** (쿼리별 상세 분석 데이터)

### C-2. 각 시트의 상세 구조

#### C-2.1 개요 시트

**목적**: 분석 항목 정의/설명 (분석서의 각 컬럼이 무엇을 의미하는지 설명)

**구조**:

- 1열: 너비 3 (공백)
- 2열: 너비 17 (항목명)
- 3열: 너비 70 (설명)
- 1행: 헤더 (대상, 설명)
- 2행부터: 항목별 설명

**포함된 항목**
패키지명, SQL ID, Mapper Path, 대상테이블, 대상컬럼, 암복호화 필요 컬럼, 암복호화 필요 Java Field, End Point, ResultMap, 클래스명, 메서드명, Model, Action, Reason, Insertion Point, Code Pattern Hint, Sql Summary

**항목 설명**

- 두 타입(ThreeStep, TypeHandler) 모두에 공용으로 사용됨
- 마이그레이션 분석 중심으로 각 항목에 대해 분석서를 보는 사람이 이해하기 쉬운 설명이 포함
- 예시:
  - SQL ID: MyBatis Mapper에서 정의된 쿼리의 고유 식별자
  - Reason: 마이그레이션 프로젝트에서 해당 코드를 변경해야 하는 사유
  - Sql Summary: 쿼리의 목적을 설명하는 요약

**포맷**:
- 폰트: 맑은 고딕, 크기 10
- 행높이: 16
- 헤더 행(1행):
  - 배경색: DFDFDF
  - 폰트: 굵은 맑은 고딕 10pt
  - 정렬: 중앙 정렬
  - 테두리: thin border 적용
- 데이터 행(2행~):
  - 2열(항목명): 왼쪽 정렬, 수직 중앙
  - 3열(설명): 왼쪽 정렬, 수직 위쪽, 줄바꿈 활성화(wrap_text=True)
  - 테두리: thin border 적용

#### C-2.2 대상목록 시트

**목적**: 암호화 대상 쿼리 및 변경 지시사항의 통합 분석

**정렬 순서**: SQL ID → Mapper Path → 대상테이블 (오름차순)

**동일 SQL ID의 다중 테이블 처리**: 동일한 SQL ID인데 테이블명이 다르면 각각 별도의 행으로 추가됨 (병합 없음)

**2행: 헤더** (modification_type에 따라 다름)

**ThreeStep 타입** (17개 컬럼):
```
패키지명, SQL ID, Mapper Path, 대상테이블, 대상컬럼, 암복호화 필요 컬럼, 암복호화 필요 Java Field,
End Point, ResultMap, 클래스명, 메서드명, Model, Action,
Reason, Insertion Point, Code Pattern Hint, Sql Summary
```

**TypeHandler 타입** (12개 컬럼):
```
패키지명, SQL ID, Mapper Path, 대상테이블, 대상컬럼, 암복호화 필요 컬럼, 암복호화 필요 Java Field,
End Point, ResultMap, 클래스명, Model, Sql Summary
```

**포맷** (공통):
- 헤더 배경색: DFDFDF
- 헤더 폰트: 굵은 맑은 고딕 10pt
- 헤더 정렬: 중앙 정렬
- 테두리: 모든 셀에 thin border
- 행 높이: 16 (기본)
- 줄바꿈: 긴 컬럼(패키지명, Reason, Insertion Point, Code Pattern Hint, Sql Summary)은 wrap_text=True

**열 너비** (ThreeStep):
```
[13, 25, 25, 25, 18, 25, 25, 25, 10, 25, 25, 25, 16, 40, 40, 40, 40]
```
(패키지명=13, SQL ID=25, Mapper Path=25, 대상테이블=25, 대상컬럼=18, 암복호화 필요 컬럼=25, 암복호화 필요 Java Field=25, End Point=25, ResultMap=10, 클래스명=25, 메서드명=25, Model=25, Action=16, Reason=40, Insertion Point=40, Code Pattern Hint=40, Sql Summary=40)

**열 너비** (TypeHandler):
```
[13, 25, 25, 25, 18, 25, 25, 25, 10, 25, 25, 40]
```
(패키지명=13, SQL ID=25, Mapper Path=25, 대상테이블=25, 대상컬럼=18, 암복호화 필요 컬럼=25, 암복호화 필요 Java Field=25, End Point=25, ResultMap=10, 클래스명=25, Model=25, Sql Summary=40)

---

## D. 상세 추출 규칙

### D-1. 패키지명

**추출 방식**: 파일 경로 기반  
**규칙**: `config.json`의 `target_project` 경로의 마지막 세그먼트(프로젝트명/레파지터리명)  
**예**: `/book-ssm-new/...` → `book-ssm-new`
**함수**: `generate_analysis_report()` 내 `repo_name = os.path.basename(os.path.normpath(target_project))`

### D-2. SQL ID

**추출 방식**: 쿼리 ID의 마지막 토큰 사용  
**규칙**: full package 형식(점 포함)인 경우 마지막 '.' 이후의 텍스트만 사용  
**예**: `com.example.BookMapper.selectBook` → `selectBook`
**함수**: `query_id.rsplit('.', 1)[-1]`

### D-3. Mapper Path

**추출 방식**: `table_access_info.json`에서 쿼리 ID와 매칭되는 SQL 쿼리 경로  
**함수**: `_find_mapper_path_for_qid(table_access, table_name, qid)`  
**반환값**: 경로의 basename만 사용 (예: `mapper/UserMapper.xml` → `UserMapper.xml`)

### D-4. 대상테이블

**추출 방식**: `step1_query_analysis.json`의 `metadata.table_name` 사용

### D-5. 대상컬럼 (테이블 전체 컬럼)

**추출 방식**: `table_access_info.json`에서 현재 테이블의 모든 컬럼  
**함수**: `_extract_table_columns_from_table_access(table_access, table_name)`  
**처리**:
1. table_access_info.json 배열의 각 요소(테이블 객체) 순회
2. table_name이 일치하는 객체 찾기
3. 해당 객체의 columns[] 추출
4. 각 column의 name 수집
5. 쉼표+공백으로 구분

**예**:
```
table_access_info.json:
{
  "table_name": "tadm00100",
  "columns": [
    {
      "name": "gvnm",
      "column_type": "dob"
    },
    {
      "name": "name",
      "column_type": "name"
    }
  ],
  "access_files": [],
  "query_type": "SELECT",
  "sql_query": "/* mapper_blocking.xml > blockedServiceList */\n\t\tSELECT\n\t\t\tTROWNUM AS rn,\n\t\t\ttsbt.ITCT_URL, ...",
  "layer": "Repository",
  "sql_queries": [
    {
      "id": "blockedServiceList",
      "query_type": "SELECT",
    }
  ]
}

Result: "gvnm, name"
```

### D-6. 암복호화 필요 컬럼

**규칙**: `step1_query_analysis.json`의 `input_mapping`과 `output_mapping` 내 `crypto_fields[].column_name` 합침  
**처리**:
1. input_mapping의 crypto_fields에서 column_name 추출
2. output_mapping의 crypto_fields에서 column_name 추출
3. 중복 제거 (순서 유지)
4. 쉼표+공백으로 구분하여 하나의 셀에 나열

**예**:
```
Input: [col1, col2]
Output: [col2, col3]
Result: "col1, col2, col3"
```

### D-7. 암복호화 필요 Java Field

**규칙**: `step1_query_analysis.json`의 `input_mapping`과 `output_mapping` 내 `crypto_fields[].java_field` 추출  
**처리**:
1. input_mapping의 crypto_fields에서 java_field 추출
2. output_mapping의 crypto_fields에서 java_field 추출
3. 중복 제거 (순서 유지)
4. 쉼표+공백으로 구분하여 하나의 셀에 나열

**예**:
```json
input_mapping: {
  "crypto_fields": [
    {"column_name": "USER_GVNM", "java_field": "userGvnm"},
    {"column_name": "USER_ID", "java_field": "userId"}
  ]
},
output_mapping: {
  "crypto_fields": [
    {"column_name": "USER_GVNM", "java_field": "userGvnm"},
    {"column_name": "PHONE", "java_field": "phone"}
  ]
}

Result: "userGvnm, userId, phone"
```

**비어있는 경우**: crypto_fields가 없거나, java_field 필드가 없으면 공백

### D-8. End Point (호출 스택의 첫 항목)

**추출 방식**: `table_access_info.json`의 sql_queries[].call_stacks에서 첫 번째 항목들 추출  
**함수**: `_extract_end_point_from_call_stacks(call_stacks)`  
**처리**:
1. call_stacks가 비어있지 않으면 순회
2. 각 call_stack의 첫 번째 항목 (index 0) 추출
3. 중복 제거 (순서 유지)
4. 쉼표+\n으로 구분

**예**:
```json
"call_stacks": [
  ["UserController1.returnVptInfo", "UserService.getUserInfo", ..., "UserMapper.getUserInfo"],
  ["UserController2.returnVptInfo", "UserService.getUserInfo", "UserMapper.getUserInfo"]
]

Result: "UserController1.returnVptInfo, UserController2.returnVptInfo"
```

**비어있는 경우**: call_stacks가 [] 또는 [] 원소가 모두 비어있으면 공백

### D-8. ResultMap

**함수**: `get_result_map(table, qid, table_access)`

**판정 로직** (중요):
```
1. table_access_info.json에서 table_name이 일치하는 객체 찾기
2. 해당 객체의 sql_queries[] 순회하여 id가 qid와 일치하는 항목 찾기
3. strategy_specific.result_map 존재 여부 및 값 확인:
   a. result_map이 없거나 빈 값 또는 null → 'X'
   b. result_map이 있고, result_field_mappings이 없거나 비어있음 → '△'
   c. result_map과 result_field_mappings이 모두 존재함 → '○'
```

**이중 검증** (중요):
- table_name 먼저 일치 확인 후, 해당 객체 내의 sql_queries만 순회 (다른 테이블의 동일 ID 쿼리와 혼동 방지)

### D-9. 클래스명

**ThreeStep**:
- 추출: `step2_planning.json`의 `modification_instructions[].class_name`
- 또는 `modification_instructions[]`에서 없으면 `file_name`에서 확장자 제거

**TypeHandler**:
- 추출 규칙: `table_access_info.json`의 `sql_queries[].call_stacks[0]`의 **마지막 항목**에서 추출
- 함수: 코드의 클래스명 추출 로직 참고
- 처리 방식:
  1. call_stacks[0] 배열의 마지막 항목 선택
  2. "ClassName.methodName" 형식을 '.' 기준으로 분리
  3. 마지막 '.'의 왼쪽 부분 = 클래스명
- 예시:
  ```json
  "call_stacks": [
    ["EmployeeController.getEmployee", "EmployeeService.getEmployee", "EmployeeMapper.getName"],
    [...]
  ]
  ```
  → 클래스명: `EmployeeMapper` (마지막 항목 `EmployeeMapper.getName`에서 추출)

### D-10. 메서드명

**ThreeStep**: 
- 추출: `step2_planning.json`의 `modification_instructions[].target_method`
- 예: `getUserInfo`, `updateUserData`

**TypeHandler**:
- 추출 규칙: `table_access_info.json`의 `sql_queries[].call_stacks[0]`의 **마지막 항목**에서 추출
- 함수: 코드의 메서드명 추출 로직 참고
- 처리 방식:
  1. call_stacks[0] 배열의 마지막 항목 선택
  2. "ClassName.methodName" 형식을 '.' 기준으로 분리
  3. 마지막 '.'의 오른쪽 부분 = 메서드명
- 예시:
  ```json
  "call_stacks": [
    ["EmployeeController.getEmployee", "EmployeeService.getEmployee", "EmployeeMapper.getName"],
    [...]
  ]
  ```
  → 메서드명: `getName` (마지막 항목 `EmployeeMapper.getName`에서 추출)

### D-10. Model

**함수**: `derive_model_common(s1, q)`
**규칙**: `step1_query_analysis.json`의 `input_mapping`과 `output_mapping`에서 `type_category`가 `VO` 또는 `MAP`인 `class_name` 수집
**처리**:
1. input_mapping 순회
2. output_mapping 순회
3. type_category == 'VO' 또는 'MAP'인 class_name 모음
4. 중복 제거, 쉼표+공백으로 구분
5. 값이 없으면 빈 문자열

### D-11. Action

**ThreeStep**:
- 추출: `step2_planning.json`의 `modification_instructions[].action`
- 예: `ADD_ENCRYPTION`, `REMOVE_ENCRYPTION`, `UPDATE_QUERY`

**TypeHandler**:
- 값: 없음 (해당 필드 미포함)

### D-12. Reason

**ThreeStep**:
- 추출: `step2_planning.json`의 `modification_instructions[].reason`
- 형식: 자유 텍스트 (줄바꿈 가능)

**TypeHandler**:
- 값: 없음 (해당 필드 미포함)

### D-13. Insertion Point

**ThreeStep**:
- 추출: `step2_planning.json`의 `modification_instructions[].insertion_point`
- 예: `METHOD_START`, `BEFORE_QUERY_EXECUTION`, `AFTER_RESULT_MAPPING`

**TypeHandler**:
- 값: 없음 (해당 필드 미포함)

### D-14. Code Pattern Hint

**ThreeStep**:
- 추출: `step2_planning.json`의 `modification_instructions[].code_pattern_hint`
- 용도: 개발자를 위한 코딩 패턴 힌트

**TypeHandler**:
- 값: 없음 (해당 필드 미포함)

### D-15. Sql Summary

**공통** (ThreeStep, TypeHandler):
- 추출: `step1_query_analysis.json`의 `result.queries[].sql_summary`
- 형식: SQL 실행 계획 또는 요약 설명

---

## E. 처리 규칙 및 로직

### E-1. 정렬 및 셀 병합

**정렬 순서** (모든 타입):
1. Primary: SQL ID (오름차순)
2. Secondary: Mapper Path (오름차순)
3. Tertiary: 대상테이블 (오름차순)

**셀 병합 규칙** (모든 타입):
```
동일한 Mapper Path를 가진 SQL ID 셀들을 Excel에서 병합

예시:
SQL ID        Mapper Path
selectUser    UserMapper.xml
selectUser    UserMapper.xml    ← SQL ID 셀 병합 (같은 Mapper Path)
insertUser    UserMapper.xml
selectOrder   OrderMapper.xml

병합 결과:
SQL ID        Mapper Path
selectUser    UserMapper.xml
              UserMapper.xml    ← SQL ID 셀 병합됨 (빈 칸)
insertUser    UserMapper.xml
selectOrder   OrderMapper.xml
```

**병합 함수**: `_merge_columns(sh, last_row)` (패키지명, 파일명, SQL ID 셀 병합)

### E-2. 진입점

**함수**: `generate_analysis_report(config: Configuration)`

**주요 단계**:
1. `config`에서 `target_project`와 `modification_type` 읽음
2. modification_type에 따라 그룹(atype/btype) 결정
   - atype (ThreeStep): `fill_target_list_modification_atype()`
   - btype (TypeHandler): `fill_target_list_modification_btype()`
3. 워크북 생성 및 시트 초기화
4. 핸들러 함수로 데이터 채우기
5. 정렬 및 셀 병합 수행
6. Excel 파일 저장

### E-2. modification_type 매칭

**지원 타입**:
```python
MODIFICATION_TYPE_GROUPS = {
    'modification_atype': {
        'types': ['ThreeStep'],
        'handler': fill_target_list_modification_atype
    },
    'modification_btype': {
        'types': ['TypeHandler', 'TypeHandler'],
        'handler': fill_target_list_modification_btype
    }
}
```

**매칭 규칙**:
- 정확 일치: `modification_type == 'ThreeStep'`
- 부분 일치 (Substring): 예: `test_ThreeStep_20260130` → `ThreeStep` 인식
- 대소문자 무시

### E-3. ThreeStep 처리 로직

**함수**: `fill_target_list_modification_atype(sh, applycrypto_root, repo_name, ...)`

**알고리즘** (table_access 기준):
```
1. applycrypto_root/three_step_results 하위의 최신 일시 폴더 찾기
2. table_access_info.json에서 모든 SQL ID 추출
   → 이 리스트의 SQL ID들을 기준으로 처리 (Master)
3. step1/step2 데이터를 사전 캐시 (모든 테이블/컨트롤러 조합)
4. table_access의 각 SQL ID에 대해:
   a. step1에서 매칭되는 query_id 찾기
   b. step2에서 매칭되는 flow 찾기
   c. step1 또는 step2에서 매칭된 데이터가 발견되면 처리 (둘 다 없으면 스킵)
5. 각 SQL ID에 대해 컬럼값 추출하여 행 추가:
   - table_access에만 있는 경우: 기본 정보만
   - step1/step2 정보 있으면: 해당 정보 추가
6. 최종 정렬 (패키지명 > 파일명 > SQL ID)
7. 패키지명, 파일명 연속 구간 셀 병합
```

**특징**:
- **기준 데이터**: table_access_info.json의 SQL ID (변경 대상 기준)
- **추가 정보**: step1/step2에서 변경 지시사항, 클래스명, 메서드명 등 보충
- **필터링 효과**: step1/step2에만 있는 SQL ID는 자동 제외
- **완전성**: table_access의 모든 SQL ID가 Excel에 포함됨 (step1/step2 미연동 여부와 무관)

**key 매칭 함수**:
```python
def qid_match_for_flow(a, b):
    # a: step2의 sql_query_id
    # b: step1의 query_id
    sa = str(a or '')
    sb = str(b or '')
    a_has_dot = '.' in sa
    b_has_dot = '.' in sb
    
    if not a_has_dot and not b_has_dot:
        return sa == sb  # 둘 다 단순명: 전체 비교
    
    return sa.rsplit('.', 1)[-1] == sb.rsplit('.', 1)[-1]  # 마지막 토큰 비교
```

### E-4. TypeHandler 처리 로직

**함수**: `fill_target_list_modification_btype(sh, applycrypto_root, repo_name, ...)`

**알고리즘**:
```
1. applycrypto_root/three_step_results 하위의 최신 일시 폴더 찾기
2. 각 [테이블명] 폴더 → 각 [컨트롤러명] 폴더 순회
3. step1_query_analysis.json만 로드 (step2 미사용)
4. table_access의 각 SQL ID에 대해:
   a. step1에서 query_id로 매칭
   b. table_access에 해당 SQL ID가 존재하면 처리 (양쪽 조건 모두 만족해야 함)
5. 각 쿼리에 대해 10개 컬럼값 추출하여 행 추가
   (메서드명, Action, Reason, Insertion Point, Code Pattern Hint 미포함)
6. 최종 정렬 (패키지명 > 파일명 > SQL ID)
7. 셀 병합 수행
```

**특징**:
- **기준 데이터**: table_access_info.json의 SQL ID (변경 대상 기준)
- **추가 정보**: step1에서 SQL 요약, 암복호화 필요 컬럼 등 보충
- **필터링 효과**: step1에만 있고 table_access에 없는 SQL ID는 자동 제외
- **완전성**: table_access에 존재하는 SQL ID만 Excel에 포함됨 (step1 연동 여부와 무관)

### E-5. 레코드 정렬

**함수**: `_sort_records(records)`

**정렬 우선순위**:
1. 패키지명 (ascending)
2. 파일명 (ascending)
3. SQL ID (ascending)

### E-6. 셀 병합

**함수**: `_merge_columns(sh, last_row)`

**병합 전략** (2단계):

#### 1단계: 패키지명(col 1) 병합
- **규칙**: 연속된 동일한 패키지명만 병합
- **동작**: row 3부터 시작, 패키지명이 변경되는 지점에서 이전 세그먼트 병합

#### 2단계: SQL ID(col 2) + Mapper Path(col 3) 통합 병합
- **규칙**: **SQL ID와 Mapper Path가 모두 같은 행들끼리만 병합**
  - SQL ID만 같고 Mapper Path가 다르면 병합하지 않음
  - Mapper Path만 같고 SQL ID가 다르면 병합하지 않음
- **대상테이블(col 4) 차이**: 무관 (테이블이 다르더라도 병합됨)
- **동작**: 
  1. row 3부터 시작하여 SQL ID와 Mapper Path 조합 추적
  2. 둘 중 하나라도 변경되면 이전 세그먼트의 SQL ID와 Mapper Path 두 컬럼을 함께 병합
  3. 다음 세그먼트 시작

**병합 예시**:

```
케이스 1: SQL ID와 Mapper Path 모두 같음 → 병합
Row | SQL ID        | Mapper Path          | 대상테이블
----|---------------|----------------------|----------
 3  | deleteEmployee| EmployeeController   | tb_employee
 4  | deleteEmployee| EmployeeController   | tb_department  ← SQL ID, Mapper Path 모두 같음 → 병합
 5  | insertUser    | EmployeeController   | tb_employee

병합 결과:
 3  | deleteEmployee| EmployeeController   | tb_employee
 4  | (병합됨)      | (병합됨)              | tb_department
 5  | insertUser    | EmployeeController   | tb_employee

케이스 2: SQL ID 같음 / Mapper Path 다름 → 병합하지 않음
Row | SQL ID        | Mapper Path          | 대상테이블
----|---------------|----------------------|----------
 6  | deleteEmployee| EmployeeController   | tb_employee
 7  | deleteEmployee| OrderController      | tb_order   ← Mapper Path 다름 → 병합 안 함
 8  | insertUser    | EmployeeController   | tb_employee

결과:
 6  | deleteEmployee| EmployeeController   | tb_employee
 7  | deleteEmployee| OrderController      | tb_order
 8  | insertUser    | EmployeeController   | tb_employee

케이스 3: SQL ID 다름 / Mapper Path 같음 → 병합하지 않음
Row | SQL ID        | Mapper Path
----|---------------|----------------------
 9  | deleteEmployee| EmployeeController
10  | selectEmployee| EmployeeController   ← SQL ID 다름 → 병합 안 함
11  | insertUser    | EmployeeController

결과:
 9  | deleteEmployee| EmployeeController
10  | selectEmployee| EmployeeController
11  | insertUser    | EmployeeController
```

**병합된 셀 정렬**: 최상단 셀에 수직 중앙 정렬 적용

### E-7. 데이터 쓰기

**함수**: `_write_to_sheet(sh, records, headers, font_default, border)`

**처리**:
1. 3행부터 데이터 시작
2. 각 레코드의 모든 컬럼값을 해당 열에 씀
3. wrap_text=True 적용 (긴 컬럼: 패키지명, Reason, Insertion Point, Code Pattern Hint, Sql Summary)
4. ResultMap 컬럼(특정 열)에만 horizontal='center' 정렬 적용

---

## F. 예외 처리 및 오류 복구

### F-1. 파일 미존재

**함수**: `safe_load_json(path, missing_files, ...)`

**처리**:
- 파일이 없으면 missing_files 리스트에 기록
- 함수는 {} (빈 딕셔너리) 반환
- 처리 계속 (에러 없음)

### F-2. JSON 파싱 오류

**처리**:
- JSON 파싱 실패 시 invalid_files 리스트에 기록
- 함수는 {} (빈 딕셔너리) 반환
- 처리 계속

### F-3. 파일 덮어쓰기 오류

**상황**: Excel 파일이 열려있어서 저장 실패  
**처리**:
1. 기존 파일 삭제 시도 (가능하면)
2. 실패 시 현재 시각 타임스탬프를 붙인 임시 파일명으로 폴백 저장
   - 예: `AsIs_Analysis_Report_ThreeStep_20250203_20250203143052.xlsx`

### F-4. 데이터 누락

**경우**:
- step2_planning.json에 해당 쿼리가 없음
- table_access_info.json에서 테이블/쿼리를 찾을 수 없음

**처리**:
- ThreeStep: step2에 없는 쿼리는 분석 대상에서 제외 (Master 원칙)
- TypeHandler: table_access_info를 먼저 확인, 없으면 빈 값으로 처리

---

## G. 포맷 및 스타일 가이드

### G-1. 폰트

- **기본**: 맑은 고딕 (Malgun Gothic), 크기 10pt
- **헤더**: 굵은 체 (bold), 10pt

### G-2. 배경색 (PatternFill)

| 용도 | 색상 코드 | 적용 대상 |
|------|---------|---------|
| 헤더 | DFDFDF | 2행 (모든 컬럼) |

### G-3. 정렬

| 항목 | 수평 | 수직 |
|------|------|------|
| 헤더 | center | center |
| 데이터 (일반) | left | center |
| ResultMap | center | center |
| 긴 텍스트 | left | top |

### G-4. 줄바꿈

**wrap_text=True 적용 컬럼**:
- Reason (ThreeStep)
- Insertion Point (ThreeStep)
- Code Pattern Hint (ThreeStep)
- Sql Summary (공통)

### G-5. 테두리

- **스타일**: thin
- **적용**: 모든 데이터 셀

### G-6. 행 높이

| 행 | 높이 |
|-----|------|
| 1행 | (자동) |
| 2행 (헤더) | (자동) |
| 3행+ (데이터) | 16 |

---

## H. 검증 및 테스트

### H-1. 단위 테스트 항목

1. **ID 매칭**:
   - 전체 ID vs 마지막 토큰 비교 로직
   - 다양한 패키지 깊이 (2~5 레벨)

2. **ResultMap 판정**:
   - result_map = null → 'X'
   - result_map 있고, result_field_mappings 없음 → '△'
   - result_field_mappings 있고, columns 중복 없음 → '□'
   - result_field_mappings 있고, columns 중복 있음 → '○ col1, col2'

3. **컬럼 추출**:
   - input_mapping + output_mapping 결합
   - 중복 제거 확인
   - 쉼표 구분 확인

4. **modification_type 매칭**:
   - "ThreeStep" 정확 일치
   - "Test_ThreeStep_20250203" 부분 일치
   - 지원 안 하는 타입 오류 처리

### H-2. 통합 테스트

1. **표준 프로젝트**:
   - ThreeStep 프로젝트로 전체 파이프라인 실행
   - 생성 파일 확인 (두 시트 모두 정상)

2. **TypeHandler 프로젝트**:
   - TypeHandler 프로젝트로 전체 파이프라인 실행
   - 컬럼 개수 확인 (12개)

3. **정렬 및 병합**:
   - 패키지명, 파일명 연속 구간 병합 확인
   - 병합 셀 정렬 (수직 가운데) 확인

4. **예외 처리**:
   - 파일 미존재 시 처리
   - JSON 파싱 오류 시 처리
   - 파일 덮어쓰기 오류 시 폴백

---

## I. 현재 구현과 명세의 비교

### I-1. 실제 구현 (현 시점)

| 항목 | 명세 상 | 실제 구현 |
|------|---------|---------|
| 입력 JSON | step1, step2, table_access (선택적) | 모두 필수 (단, step2는 ThreeStep만) |
| modification_type | 엄격한 일치 | 부분 일치 지원 (substring) |
| 출력 시트 수 | 1개 (대상목록) | 2개 (대상테이블_컬럼 + 대상목록) |
| 셀 병합 | 패키지명, 파일명 | 구현됨 |
| ResultMap 로직 | 3가지 상태 | 3가지 상태 (X, △, ○) 정확히 구현 |
| 오류 처리 | 경고 후 계속 | 구현됨 (missing_files, invalid_files 기록) |
| 파일 덮어쓰기 | 기본 덮어쓰기 | 충돌 시 타임스탬프 붙임 |

### I-2. 발견된 차이

1. **대상테이블_컬럼 시트**: 원명세에 명시 없음 (실제로는 생성)
2. **modification_type 유연성**: 원명세는 엄격함 (실제는 substring 매칭)
3. **파일 출력명**: 원명세 `asis_analysis_report_YYYYMMDD.xlsx` → 실제 `AsIs_Analysis_Report_{TYPE}_{YYYYMMDD}.xlsx` (타입 포함)

### I-3. 향후 개선 권장 사항

1. 대상테이블_컬럼 시트 용도 명확화 (현재는 템플릿 느낌)
2. modification_type substring 매칭 명세에 명시
3. 파일명 타입 포함 여부 명세 갱신
4. 데이터 유효성 검사 강화 (예: NULL, 빈 문자열 통일)

---

## J. 실행 예시

### J-1. ThreeStep 분석

```bash
python main.py generate-analysis_report --config config.json
# config.json의 modification_type = "ThreeStep"
```

**동작**:
1. three_step_results의 최신 폴더 탐색
2. step1 + step2 데이터 결합
3. 17개 컬럼 분석서 생성
4. 출력: `AsIs_Analysis_Report_ThreeStep_20250203.xlsx`

### J-2. TypeHandler 분석

```bash
python main.py generate-analysis_report --config config.json
# config.json의 modification_type = "TypeHandler"
```

**동작**:
1. three_step_results의 최신 폴더 탐색
2. step1 데이터만 사용
3. 12개 컬럼 분석서 생성
4. 출력: `AsIs_Analysis_Report_TypeHandler_20250203.xlsx`

---

## K. 함수 레퍼런스

### K-1. 주요 진입 함수

```python
def generate_analysis_report(config: Configuration) -> str:
    """AS-IS 분석서 생성기 래퍼 함수
    
    Returns: 생성된 Excel 파일 경로
    """
```

### K-2. 워크북/시트 생성 함수

```python
def create_target_table_column(wb, font_default, bold_font, border, title) -> Worksheet:
    """대상테이블_컬럼 시트 생성"""

def create_target_list(wb, font_default, bold_font, border, title, widths, headers) -> Worksheet:
    """대상목록 시트 생성 및 헤더 설정"""
```

### K-3. 데이터 채우기 함수

```python
def fill_target_list_modification_atype(sh, applycrypto_root, repo_name, font_default, border, headers) -> tuple:
    """ThreeStep 분석서 데이터 채우기
    
    Returns: (worksheet, records)
    """

def fill_target_list_modification_btype(sh, applycrypto_root, repo_name, font_default, border, headers) -> tuple:
    """TypeHandler 분석서 데이터 채우기
    
    Returns: (worksheet, records)
    """
```

### K-4. 유틸리티 함수

```python
def get_result_map(table, qid, table_access) -> str:
    """ResultMap 상태 판정
    
    Returns: 'X', '△', '○'
    """

def derive_model_common(s1, q) -> str:
    """Model 컬럼값 추출 (VO/MAP 타입 수집)"""

def _find_mapper_path_for_qid(table_access, table_name, qid) -> str:
    """Mapper 경로 찾기"""

def safe_load_json(path, missing_files, invalid_files, applycrypto_root) -> dict:
    """JSON 안전 로드 (오류 로깅)"""

def _sort_records(records) -> None:
    """레코드 정렬 (패키지명 > 파일명 > SQL ID)"""

def _write_to_sheet(sh, records, headers, font_default, border) -> int:
    """시트에 레코드 작성
    
    Returns: 마지막 작성 행 번호
    """

def _merge_columns(sh, last_row) -> None:
    """패키지명, 파일명 열 병합"""

def _print_summary(missing_files, invalid_files) -> None:
    """누락/오류 파일 요약 출력"""

def make_border() -> Border:
    """thin border 스타일 생성"""

def set_row_height(ws, height) -> None:
    """시트 모든 행의 높이 설정"""
```

---

**문서 작성일**: 2025년 2월 3일  
**버전**: 2.1 (SQL ID 검증 기능 추가)  
**상태**: analysis_report_generator.py v2.1+ 호환

---

## D. SQL ID 데이터 검증 기능

### D-1. 개요

엑셀에 작성된 SQL Query ID가 누락되지 않았는지 검증하는 기능입니다. `table_access_info.json`에 존재하는 모든 SQL ID가 실제 분석 JSON 파일(step1_query_analysis.json, step2_planning.json)에 존재하는지 확인합니다.

### D-2. 검증 기준

#### atype (ThreeStep)
- **검증 대상**: step1_query_analysis.json + step2_planning.json
- **조건**: SQL ID가 **step1과 step2 모두에 존재**해야 OK
- 하나라도 없으면 MISSING으로 표시

#### btype (TypeHandler / TypeHandler)
- **검증 대상**: step1_query_analysis.json **만**
- **조건**: SQL ID가 **step1에만 존재**하면 OK
- step2는 N/A (검증하지 않음)

### D-3. 검증 로그 파일

**파일명**: `log_AsIs_Analysis_Report_{modification_type}_{YYYYMMDD}.csv`

**저장 위치**: 엑셀 파일과 동일한 artifacts 디렉터리
```
{target_project}/.applycrypto/artifacts/
  ├── AsIs_Analysis_Report_ThreeStep_20260203.xlsx
  └── log_AsIs_Analysis_Report_ThreeStep_20260203.csv
```

**파일 형식**: UTF-8 BOM으로 인코딩된 CSV

**CSV 컬럼**:
| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| 테이블명 | 대상 테이블 이름 | tb_employee |
| SQL ID | table_access_info.sql_queries.id | selectEmployeeList |
| step1 존재여부 | step1_query_analysis.json의 query_id 존재 여부 | [OK] 또는 [NG] |
| step2 존재여부 | step2_planning.json의 sql_query_id 존재 여부 (atype만) | [OK], [NG], 또는 [N/A] |
| 상태 | 검증 결과 | OK 또는 MISSING |

### D-4. 검증 로직

#### D-4.1 SQL ID 매칭 규칙

SQL ID는 **마지막 토큰(점 기준)으로 비교**합니다:

```
table_access_info: "com.example.mapper.EmployeeMapper.selectById"
step1_query_analysis: "selectById"
→ 일치 (마지막 토큰 비교)
```

#### D-4.2 검증 흐름

1. **table_access_info.json 로드**: 테이블별 sql_queries 리스트 추출
2. **step1_query_analysis.json 로드**: 각 테이블의 query_id 수집
3. **step2_planning.json 로드** (atype만): 각 테이블의 sql_query_id 수집
4. **SQL ID별 매칭**: 마지막 토큰으로 존재 여부 확인
5. **검증 판정**:
   - **atype**: step1과 step2 모두 [OK]이면 상태=OK, 하나라도 [NG]이면 MISSING
   - **btype**: step1 [OK]이면 상태=OK, [NG]이면 MISSING (step2는 검증 안함)
6. **CSV 저장**: 검증 결과를 CSV 파일로 기록

### D-5. 실행 예시

**명령어**:
```bash
python main.py generate-analysis_report --config config.json
```

**출력**:
```
- SQL ID 데이터 검증 시작
  [SQL ID 검증] modification_type: ThreeStep
  [SQL ID 검증] 테이블: tb_employee | SQL ID: selectEmployeeList | step1: [OK] | step2: [OK] | OK
  [SQL ID 검증] 테이블: tb_employee | SQL ID: insertEmployee | step1: [OK] | step2: [OK] | OK
  ...
  [SQL ID 검증] 총 검사: 14개, 누락: 0개
- SQL ID 검증 로그: C:\Project\SSLife\book-ssm\.applycrypto\artifacts\log_AsIs_Analysis_Report_ThreeStep_20260203.csv
- SQL ID 데이터 검증 완료 (이상 없음)
```

### D-6. 구현 함수

#### `_validate_sql_id_existence(applycrypto_root, modification_type, output_dir=None)`

**매개변수**:
- `applycrypto_root`: `.applycrypto` 루트 경로
- `modification_type`: 'ThreeStep' 또는 'TypeHandler'
- `output_dir`: CSV 저장 디렉터리 (artifacts 디렉터리)

**반환값**:
- `True`: 모든 SQL ID가 검증됨 (누락 없음)
- `False`: 누락된 SQL ID 있음

**주요 동작**:
1. CSV 헤더 생성: [테이블명, SQL ID, step1 존재여부, step2 존재여부, 상태]
2. table_access_info.json의 각 테이블별 sql_queries 반복
3. step1/step2에서 query_id 수집 (마지막 토큰 기준)
4. SQL ID별 검증 수행
5. CSV 파일로 결과 저장
6. finally 블록에서 CSV 파일 기록 (UTF-8 BOM)

---

## E. Implementation notes (실제 구현 특이사항):

- 진입점: 코드의 진입점은 `generate_analysis_report(config: Configuration)`이며, `config.target_project`의 `{target_project}\.applycrypto`를 기준으로 동작합니다.
- `three_step_results` 하위에 여러 타임스탬프(일시)가 존재하면 코드에서는 디렉터리명을 정렬한 뒤 마지막 항목(가장 최신으로 가정)을 사용합니다.
- 전역 참조 파일: `{target_project}\.applycrypto\results\table_access_info.json`을 참조하여 `ResultMap` 여부와 매퍼/소스 경로를 판별합니다. 이 파일이 없거나 파싱 실패 시에는 로그/요약에 파싱 오류를 보고하되 전체 프로세스를 중단하지 않습니다.
- `modification_type` 처리: 코드에서는 내부 그룹 매핑(예: `ThreeStep` → atype, `TypeHandler`/`TypeHandler` → btype)을 사용하며, 입력값에 대해 키워드 부분 일치(substring, case-insensitive)를 허용해 유연하게 canonical type으로 변환합니다.
- `ResultMap` 반환 규칙: `table_access_info.json` 내 `sql_queries[].strategy_specific`에 `result_map`이 없으면 `'X'`, `result_map`은 있으나 `result_field_mappings`이 없으면 `'△'`, 둘 다 존재하면 `'○'`를 반환합니다.
- Mapper Path 휴리스틱: `table_access_info.json`의 후보 필드(`source_file_path`, `source_file`, `source_file_paths`, `access_files`, `call_stacks`)를 우선순위로 확인하여 매퍼/소스 경로를 반환합니다. 구현상 매퍼 XML(.xml) 또는 매퍼 Java 인터페이스(파일명에 `Mapper` 포함)를 우선 선호하도록 설계되어 있습니다.
- 안전한 JSON 로드: `safe_load_json`은 빈 파일, 누락 파일, JSON 파싱 오류를 구분하여 각각 로그에 기록하고 `None`을 반환합니다. 실행 요약에 누락/파싱 오류 건수가 출력됩니다.
- 출력 파일: 기본 출력 경로는 `{target_project}\.applycrypto\artifacts\AsIs_Analysis_Report_{modification_type}_{YYYYMMDD}.xlsx`입니다. 저장 시 PermissionError 등으로 실패하면 타임스탬프를 붙인 임시 파일명으로 폴백합니다.
