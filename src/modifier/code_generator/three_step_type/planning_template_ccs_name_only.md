# Encryption/Decryption Modification Planning (Phase 2) - CCS Version (Name Only)

## Role

You are an expert in analyzing **Data Flow** in Java Spring Boot legacy systems.
Based on the information below, output specific modification instructions in JSON format describing **where**, **what**, and **how** to insert encryption/decryption logic.

**Important**: Your role is **analysis and planning**. Actual code writing will be done in the next step.
**This template focuses ONLY on NAME fields** - use `SliEncryptionConstants.Policy.NAME` for all operations.

**★★★ IMPORTANT: Preserve Existing Encryption ★★★**
- This template adds NAME field encryption/decryption ONLY
- Existing encryption for other fields (DOB, RRN, TEL_NO, etc.) MUST remain unchanged
- Only add new NAME-specific crypto logic; do NOT modify existing crypto code
- If a method already has encryption/decryption for other fields, add NAME encryption alongside it

---

## Encryption Framework Information (SLI Encryption)

This project uses the **SLI Encryption Framework** with static utility methods:

### Required Imports

```java
import sli.fw.online.SliEncryptionUtil;
import sli.fw.online.constants.SliEncryptionConstants;
```

### Encryption/Decryption Methods

**Encryption** - `SliEncryptionUtil.encrypt()`:
- `String encrypt(String policyId, String targetStr)` - Basic encryption
- `String encrypt(String policyId, String targetStr, boolean isDB)` - With DB flag (use `true`)
- `List<SliEncryptionVO> encrypt(List<SliEncryptionVO> targetVOList)` - Batch encryption
- `List<SliEncryptionVO> encrypt(List<SliEncryptionVO> targetVOList, boolean isDB)` - Batch with DB flag

**Decryption** - `SliEncryptionUtil.decrypt()`:
- `String decrypt(int targetSystem, String policyId, String targetStr)` - Basic decryption (use `0` for targetSystem)
- `String decrypt(int targetSystem, String policyId, String targetStr, boolean isDB)` - With DB flag (use `true`)
- `List<SliEncryptionVO> decrypt(int targetSystem, List<SliEncryptionVO> targetVOList)` - Batch decryption
- `List<SliEncryptionVO> decrypt(int targetSystem, List<SliEncryptionVO> targetVOList, boolean isDB)` - Batch with DB flag

**IMPORTANT**:
- `SliEncryptionUtil` methods are **static** - NO `@Autowired` injection needed
- For `decrypt()`, always use `targetSystem = 0`
- When using `isDB` parameter, always set it to `true`

### Policy ID Determination (★★★ CRITICAL - NAME ONLY ★★★)

**This template processes ONLY name fields. Always use:**

`SliEncryptionConstants.Policy.NAME`

### Policy Constant Reference Table (Name Only)

| Field Type                     | column_type | Policy Constant                          | Column Name Patterns                                                     |
| ------------------------------ | ----------- | ---------------------------------------- | ------------------------------------------------------------------------ |
| **Name (이름)**                | `name`      | `SliEncryptionConstants.Policy.NAME`     | name, userName, user_name, fullName, firstName, lastName, custNm, CUST_NM, empNm, EMP_NM, gvnm, aenam |

### ★★★ CRITICAL: Role of table_info vs mapping_info ★★★

**`table_info.columns`**: Project-level configuration - columns that MAY need encryption/decryption
- Used to confirm the column is a name type
- Does NOT mean every query must encrypt/decrypt these columns

**`mapping_info.crypto_fields`**: Query-level analysis result from Phase 1 - columns that ACTUALLY need encryption/decryption for each specific query
- **THIS IS THE SOURCE OF TRUTH** for what to encrypt/decrypt
- If `crypto_fields` is empty for a query → that query does NOT need encryption/decryption for this table

**Important Distinction:**
- `table_info.columns`: Reference for confirming name type (e.g., `gvnm` → `column_type: "name"` → `SliEncryptionConstants.Policy.NAME`)
- `mapping_info.crypto_fields`: **Actual fields to process** - analyzed in Phase 1 (e.g., `gvnm` → `java_field: "aenam"`)

**⚠️ DO NOT INVENT crypto_fields!** If Phase 1 returned empty `crypto_fields` for a query, trust it. Do NOT add fields just because they exist in `table_info.columns`.

---

## CCS Utility Classes (★★★ CRITICAL for CCS Projects ★★★)

This project uses CCS-specific utility classes for encryption/decryption wrappers with null-safety.

### Configured Utility Classes
{{ ccs_util_info }}

### Single-Record Encryption Pattern (★ CRITICAL: Null-safe wrapper)

**For ENCRYPT action - Use `{{ common_util }}.getDefaultValue()` wrapper:**
```java
String nameEncr = "";
nameEncr = {{ common_util }}.getDefaultValue(
    !StringUtil.isEmptyTrimmed(inputVO.get{Field}()),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, inputVO.get{Field}(), true),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, " ", true)
);
inputVO.set{Field}(nameEncr);
```

**Explanation:**
- First parameter: null/empty check condition
- Second parameter: encryption result if not empty
- Third parameter: encrypted space (" ") if empty - maintains encrypted format

### Single-Record Decryption Pattern (★ CRITICAL: Null-safe wrapper)

**For DECRYPT action - Use `{{ common_util }}.getDefaultValue()` wrapper:**
```java
String nameDecr = "";
nameDecr = {{ common_util }}.getDefaultValue(
    !StringUtil.isEmptyTrimmed(outputVO.get{Field}()),
    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, outputVO.get{Field}(), true),
    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, " ", true)
);
outputVO.set{Field}(nameDecr);
```

**getDefaultValue implementation:**
```java
public static String getDefaultValue(boolean flag, String value, String defaultValue) {
    return flag ? value : defaultValue;
}
```

### Multi-Record Decryption Pattern (★ For List results - DECRYPT_LIST action)

**IMPORTANT: This pattern is for DECRYPTION ONLY (online systems don't batch-encrypt multiple names)**

**Step 1: Decrypt using setListDecryptAndMask**
```java
Map<String, String> targetEncr = new HashMap<String, String>();
targetEncr.put("{javaField1}", SliEncryptionConstants.Policy.NAME);
targetEncr.put("{javaField2}", SliEncryptionConstants.Policy.NAME);
outSVOs = (List<{VOType}>) {{ common_util }}.setListDecryptAndMask(outSVOs, targetEncr);
```

**Step 2: Mask name fields separately (setListDecryptAndMask doesn't mask names)**
```java
for (int i = 0; i < outSVOs.size(); i++) {
    outSVOs.get(i).set{Field1}Mask({{ masking_util }}.mask(SliMaskingConstant.NAME, outSVOs.get(i).get{Field1}()));
    outSVOs.get(i).set{Field2}Mask({{ masking_util }}.mask(SliMaskingConstant.NAME, outSVOs.get(i).get{Field2}()));
}
```

### Multi-Record Decryption WITHOUT Masking

**Use third parameter `false` when masking should NOT be applied:**

```java
Map<String, String> targetEncr = new HashMap<String, String>();
targetEncr.put("wrtr", SliEncryptionConstants.Policy.NAME);
// Third parameter 'false' disables masking - no need for separate masking loop
outSVOs = (List<{VOType}>) {{ common_util }}.setListDecryptAndMask(outSVOs, targetEncr, false);
```

**When to use `false` (no masking):**
- Data is displayed in internal admin system (관리자 화면)
- Data is used for further processing/calculations
- Export to external systems that need plaintext

**When to use default (with masking):**
- Data is displayed to end users (고객 화면 출력)
- Security/privacy requirements mandate masking

### When to Use Each Pattern

| Scenario | Pattern | Action |
|----------|---------|--------|
| Single VO encryption | Single-Record Encryption | `ENCRYPT` |
| Single VO decryption | Single-Record Decryption | `DECRYPT` |
| List<VO> decryption (with masking) | setListDecryptAndMask + mask loop | `DECRYPT_LIST` |
| List<VO> decryption (no masking) | setListDecryptAndMask(..., false) | `DECRYPT_LIST` |
| Existing for-loop iterating List | Single-Record inside loop | `DECRYPT` |

**Decision rule for List decryption:**
- If code already has a for-loop iterating the list → use Single-Record pattern inside the loop
- If no existing for-loop → use Multi-Record pattern (setListDecryptAndMask + masking loop)
- If no masking needed → use Multi-Record pattern with third parameter `false`

---

## Analysis Target Information

### ★★★ Target Table/Column Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table specified below.**

This is the specific table that requires encryption/decryption modifications. Analyze the data flow ONLY for operations involving this table.

{{ table_info }}

**table_info.columns Structure:**

Each column in `table_info.columns` may contain:
- `name`: Column name (always present)
- `new_column`: Whether this is a new column (boolean)
- `column_type`: Should be `"name"` for this template
- `encryption_code`: Direct policy constant to use - e.g., `"SliEncryptionConstants.Policy.NAME"` (optional but highest priority)

**Example:**
```json
{
  "table_name": "TB_BANNER",
  "columns": [
    { "name": "gvnm", "new_column": false, "column_type": "name", "encryption_code": "SliEncryptionConstants.Policy.NAME" }
  ]
}
```

**Instructions:**

1. **Trust `mapping_info.crypto_fields`** - this is Phase 1's analysis result. If it's empty, NO encryption/decryption needed for that query
2. All name columns use `SliEncryptionConstants.Policy.NAME`
3. Analyze queries from `mapping_info.queries[]` (NOT raw SQL - SQL was analyzed in Phase 1)
4. Only analyze methods that are part of call chains in `call_stacks`
5. Generate modification instructions ONLY for files in `source_files`
6. **If `crypto_fields` is empty** → output `action: "SKIP"` with appropriate reason

**IMPORTANT: SQL queries are NOT provided directly in this phase.**
Use `mapping_info` from Phase 1 which contains pre-analyzed query information including:
- `query_id`: Which query is being called
- `command_type`: SELECT/INSERT/UPDATE/DELETE
- `crypto_fields`: Which fields need encryption/decryption with their Java field names

### Data Mapping Summary (★ Pre-analyzed from Phase 1)

The following `mapping_info` was extracted in Phase 1 and contains all SQL query analysis results.

**★★★ CRITICAL: Trust Phase 1 Results ★★★**

- If `input_mapping.crypto_fields` is empty → NO encryption needed for input
- If `output_mapping.crypto_fields` is empty → NO decryption needed for output
- If BOTH are empty → `action: "SKIP"` (this query doesn't involve target columns)
- **DO NOT invent or add fields** that weren't identified in Phase 1

**mapping_info Structure:**

```json
{
  "summary": {
    "total_queries": 3,
    "encryption_needed_count": 2
  },
  "queries": [
    {
      "query_id": "com.example.mapper.UserMapper.selectUser",
      "command_type": "SELECT | INSERT | UPDATE | DELETE",
      "sql_summary": "Brief description of query purpose with target columns",
      "input_mapping": {
        "type_category": "VO | MAP | PRIMITIVE | NONE",
        "class_name": "Simple class name (e.g., UserVO, HashMap)",
        "crypto_fields": [
          {
            "column_name": "DB column name",
            "java_field": "Java field name or Map key",
            "getter": "getXxx (only for VO with provided VO file)",
            "setter": "setXxx (only for VO with provided VO file)"
          }
        ]
      },
      "output_mapping": {
        "type_category": "VO | MAP | PRIMITIVE | NONE",
        "class_name": "Simple class name",
        "crypto_fields": [...]
      }
    }
  ]
}
```

**Key Fields to Use:**

| Field | Description | How to Use |
|-------|-------------|------------|
| `query_id` | Matches DAO/Mapper method name | Match with call chain to identify which query is called |
| `command_type` | SQL command type | `SELECT` → DECRYPT results, `INSERT/UPDATE` → ENCRYPT inputs |
| `sql_summary` | Query purpose description | Understand what the query does |
| `crypto_fields` | Array of fields needing encryption | Contains `column_name`, `java_field`, and optional `getter/setter` |
| `java_field` | Field name (VO) or Map key | Use for code generation (e.g., `vo.getJavaField()` or `map.get("java_field")`) |
| `getter/setter` | Methods for VO types (optional) | Use directly in code_pattern_hint; **only present when VO file was provided in Phase 1** |

**Determining ENCRYPT/DECRYPT action:**

Based on `command_type` and mapping location:
- `input_mapping` fields with `INSERT/UPDATE` command → ENCRYPT before DB operation
- `output_mapping` fields with `SELECT` command → DECRYPT after DB operation
- `input_mapping` fields used in WHERE clause → ENCRYPT (search parameter must match encrypted DB data)

**For Map types with aliases:**

When SQL uses aliases (e.g., `SELECT emp_nm AS name`), `java_field` contains the alias:
```json
{
  "column_name": "emp_nm",
  "java_field": "name"
}
```
Use the alias for Map operations: `map.get("name")` / `map.put("name", ...)`

{{ mapping_info }}

### Method Call Chain (Endpoint → SQL)

Call path from controller to SQL:
{{ call_stacks }}

### Source Files to Modify

{{ source_files }}

---

## Analysis Guidelines

### 1. Data Flow Analysis (Per Call Chain)

**For each call chain in call_stacks**, analyze the data flow:

1. Find the matching SQL query in `mapping_info.queries` by matching `query_id` with DAO method.
2. **Check if `crypto_fields` is empty:**
   - If BOTH `input_mapping.crypto_fields` AND `output_mapping.crypto_fields` are empty → `action: "SKIP"`
   - **DO NOT assume** encryption/decryption is needed just because the query touches the target table
3. If `crypto_fields` has entries, use `command_type` and mapping location to determine crypto action:
   - `INSERT/UPDATE` command with `input_mapping.crypto_fields` → **ENCRYPT** before DAO call
   - `SELECT` command with `output_mapping.crypto_fields` → **DECRYPT** after DAO returns
   - `SELECT` command with `input_mapping.crypto_fields` (WHERE clause) → **ENCRYPT** search param first
4. All name fields use `SliEncryptionConstants.Policy.NAME`.

### 2. Using Data Mapping (from mapping_info)

**If Input/Output is a VO:**

- **With `getter`/`setter` provided**: Use CCS utility wrapper patterns
  - ENCRYPT Example:
    ```java
    String empNmEncr = "";
    empNmEncr = {{ common_util }}.getDefaultValue(
        !StringUtil.isEmptyTrimmed(vo.getEmpNm()),
        SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm(), true),
        SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, " ", true)
    );
    vo.setEmpNm(empNmEncr);
    ```
  - DECRYPT Example:
    ```java
    String empNmDecr = "";
    empNmDecr = {{ common_util }}.getDefaultValue(
        !StringUtil.isEmptyTrimmed(vo.getEmpNm()),
        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, vo.getEmpNm(), true),
        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, " ", true)
    );
    vo.setEmpNm(empNmDecr);
    ```
- **Without `getter`/`setter`** (VO file wasn't provided in Phase 1): Infer from `java_field`
  - Assume standard JavaBean conventions: `getXxx()` / `setXxx()`

**If Input/Output is a Map:**

- Use `java_field` as the Map key (this includes aliases if SQL uses them)
- DECRYPT Example:
  ```java
  String nameDecr = "";
  nameDecr = {{ common_util }}.getDefaultValue(
      !StringUtil.isEmptyTrimmed((String)map.get("name")),
      SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, (String)map.get("name"), true),
      SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, " ", true)
  );
  map.put("name", nameDecr);
  ```

**If Input/Output is Primitive:**

- It's a single value (e.g., String param). Use CCS utility wrapper.
- ENCRYPT Example:
  ```java
  String empNmEncr = "";
  empNmEncr = {{ common_util }}.getDefaultValue(
      !StringUtil.isEmptyTrimmed(empNm),
      SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, empNm, true),
      SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, " ", true)
  );
  empNm = empNmEncr;
  ```

### 3. Modification Location Decision (★ CRITICAL: Service Layer Priority)

**IMPORTANT: Always prioritize Service layer for encryption/decryption logic.**

**Why Service Layer First?**
1. **Consistency**: The same file may appear in multiple modification contexts (different tables). Consistent placement in Service layer prevents duplicate encryption/decryption.
2. **Separation of Concerns**: Controller handles HTTP request/response only. Service handles business logic including encryption/decryption.
3. **Maintainability**: All crypto logic in one layer makes it easier to audit and maintain.

**Decision Rules:**
| Call Chain Pattern | Modification Location | Reason |
|-------------------|----------------------|--------|
| Controller → Service → DAO | **Service** (preferred) | Standard pattern, crypto in Service |
| Controller → DAO (no Service) | Controller | No Service layer exists |
| Service → DAO (no Controller) | Service | Batch/scheduled job pattern |

**⚠️ WARNING: Never add crypto logic to BOTH Controller AND Service for the same data flow!**
This causes double encryption/decryption which corrupts data.

```java
// ❌ WRONG: Crypto in both layers
// Controller
String nameEncr = {{ common_util }}.getDefaultValue(!StringUtil.isEmptyTrimmed(vo.getName()),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getName(), true),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, " ", true));
vo.setName(nameEncr);  // First encryption
employeeService.save(vo);

// Service
String nameEncr2 = {{ common_util }}.getDefaultValue(!StringUtil.isEmptyTrimmed(vo.getName()),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getName(), true),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, " ", true));
vo.setName(nameEncr2);  // Double encryption! DATA CORRUPTED!
employeeDao.insert(vo);

// ✅ CORRECT: Crypto only in Service layer
// Controller - NO crypto logic
employeeService.save(vo);

// Service - crypto logic HERE using CCS utility wrapper
String nameEncr = "";
nameEncr = {{ common_util }}.getDefaultValue(
    !StringUtil.isEmptyTrimmed(vo.getName()),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getName(), true),
    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, " ", true)
);
vo.setName(nameEncr);
employeeDao.insert(vo);
```

**When to SKIP Controller files:**
- If the call chain includes a Service layer, mark Controller modifications as `action: "SKIP"` with reason: "Encryption/decryption handled in Service layer"

### 4. Minimize Modification Scope

- Maintain existing code structure and logic as much as possible
- Only add encryption/decryption logic
- Do not modify unnecessary files

---

## Output Format (★★★ CRITICAL: JSON ONLY ★★★)

**IMPORTANT OUTPUT RULES:**
1. Output **ONLY** valid JSON - no explanations, no markdown, no comments before or after
2. Do **NOT** include ```json or ``` markers
3. Do **NOT** add trailing commas (e.g., `{"a": 1,}` is INVALID)
4. Do **NOT** include JavaScript-style comments (`//` or `/* */`)
5. Use **double quotes** for all strings and keys
6. Ensure all brackets and braces are properly closed
7. Use `null` instead of `undefined` or empty values

**Expected JSON Structure:**
```json
{
  "data_flow_analysis": {
    "overview": "Overview of the entire data flow (2-3 sentences)",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "User Registration Flow",
        "sql_query_id": "com.example.mapper.UserMapper.insertUser",
        "direction": "INBOUND_TO_DB | DB_TO_OUTBOUND | BIDIRECTIONAL",
        "data_source": {
          "type": "HTTP_REQUEST | SESSION | DB | EXTERNAL_API",
          "description": "Where the data comes from"
        },
        "data_sink": {
          "type": "DB | HTTP_RESPONSE | SESSION | EXTERNAL_API",
          "description": "Where the data goes to"
        },
        "path": "Controller.method() → Service.method() → DAO.method() → DB",
        "sensitive_columns": ["emp_nm", "cust_nm"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001 (matches data_flow_analysis.flows[].flow_id)",
      "file_name": "File name (e.g., UserService.java)",
      "target_method": "Method name to modify",
      "action": "ENCRYPT | DECRYPT | DECRYPT_LIST | ENCRYPT_THEN_DECRYPT | SKIP",
      "reason": "Reason for this modification (or reason for SKIP)",
      "target_properties": ["empNm", "custNm"],
      "insertion_point": "Code insertion location description (e.g., 'right before dao.insert(list) call')",
      "code_pattern_hint": "Code pattern hint to insert"
    }
  ]
}
```

### BIDIRECTIONAL Flow Structure

For `direction: "BIDIRECTIONAL"` (e.g., search with encrypted WHERE + decrypted result), use nested objects for each direction:

```json
{
  "flow_id": "FLOW_001",
  "flow_name": "Customer Search with Encrypted WHERE",
  "sql_query_id": "com.example.mapper.CustomerMapper.selectByName",
  "direction": "BIDIRECTIONAL",
  "INBOUND_TO_DB": {
    "data_source": {
      "type": "HTTP_REQUEST",
      "description": "Search parameter (name) from user input"
    },
    "data_sink": {
      "type": "DB",
      "description": "Query executes against encrypted DB data"
    }
  },
  "DB_TO_OUTBOUND": {
    "data_source": {
      "type": "DB",
      "description": "Encrypted results from database"
    },
    "data_sink": {
      "type": "HTTP_RESPONSE",
      "description": "Decrypted results returned to client"
    }
  },
  "path": "Controller → Service.search() → DAO → DB → Service → Controller → Client",
  "sensitive_columns": ["cust_nm"]
}
```

### Field Descriptions

| Field               | Description                                              | Example                                                       |
| ------------------- | -------------------------------------------------------- | ------------------------------------------------------------- |
| `flow_id`           | Reference to data_flow_analysis.flows[].flow_id          | `FLOW_001`, `FLOW_002`                                        |
| `sql_query_id`      | Matching query_id from mapping_info.queries[]            | `com.example.mapper.UserMapper.insertUser`                    |
| `file_name`         | File name to modify                                      | `UserService.java`, `EmpController.java`                      |
| `target_method`     | Method name to modify                                    | `saveUser`, `getUserList`                                     |
| `action`            | Action to perform                                        | `ENCRYPT`, `DECRYPT`, `DECRYPT_LIST`, `ENCRYPT_THEN_DECRYPT`, `SKIP` |
| `target_properties` | Properties to encrypt/decrypt (array of strings)         | `["empNm", "custNm"]`                                         |
| `insertion_point`   | Insertion location description                           | `right before dao.insert() call`, `right before return list;` |
| `code_pattern_hint` | Code pattern example                                     | `vo.setEmpNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm()));` |

### ⚠️ CRITICAL: Every Flow MUST Have a modification_instruction Entry ⚠️

**For EVERY flow in `data_flow_analysis.flows`, you MUST output a corresponding entry in `modification_instructions`.**

- If the flow requires encryption/decryption → output with `action: "ENCRYPT"` or `action: "DECRYPT"`
- If the flow does NOT require modification → output with `action: "SKIP"` and explain `reason`

**DO NOT skip any flow!** The Execution phase relies on explicit SKIP entries to know which flows were analyzed and intentionally skipped.

**Example:** If `data_flow_analysis.flows` contains FLOW_001, FLOW_002, FLOW_003, then `modification_instructions` MUST contain entries for ALL three flows (even if some are SKIP).

### Important Notes

1. **sql_query_id**: Copy the exact `query_id` from `mapping_info.queries[]` that corresponds to this flow. Match the DAO method in `call_stacks` with `query_id` in `mapping_info`. If no DB access (e.g., Session → HTTP_RESPONSE), use `null`.
2. **When action is SKIP**: Specify in `reason` which flow (flow_id) this refers to and why no modification is needed
3. **target_properties**: Array of `java_field` names (strings) from `crypto_fields`. Use the Java field name, not DB column name.
4. **insertion_point**: Describe specifically so code can be inserted in the next step
5. **code_pattern_hint**:
   - For VO with getter/setter: Use them directly (e.g., `vo.setEmpNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm()));`)
   - For VO without getter/setter: Infer from java_field (e.g., `java_field: "empNm"` → `vo.setEmpNm(...)`)
   - For Map: Use java_field as key (e.g., `map.put("name", SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, (String)map.get("name")));`)
6. **Use mapping_info.crypto_fields**: Reference `java_field`, and `getter`/`setter` (if present) for accurate code patterns
7. **Always use `SliEncryptionConstants.Policy.NAME`** for all encryption/decryption operations

---

## Critical Encryption/Decryption Rules

### Core Principle: Encrypt/Decrypt ONLY when data crosses the DB boundary

| Data Source  | Data Sink     | Action      | Reason                                                            |
| ------------ | ------------- | ----------- | ----------------------------------------------------------------- |
| HTTP_REQUEST | DB            | **ENCRYPT** | Plaintext from client must be encrypted before DB storage         |
| DB           | HTTP_RESPONSE | **DECRYPT** | Encrypted data from DB must be decrypted before sending to client |
| DB           | EXTERNAL_API  | **DECRYPT** | External systems expect plaintext data                            |
| EXTERNAL_API | DB            | **ENCRYPT** | Data from external systems must be encrypted before DB storage    |
| SESSION      | DB            | **ENCRYPT** | Session data is plaintext, must be encrypted for DB               |
| DB           | SESSION       | **DECRYPT** | Encrypted DB data must be decrypted for session storage           |
| SESSION      | HTTP_RESPONSE | **NONE**    | Session data is already plaintext, no decryption needed           |
| HTTP_REQUEST | SESSION       | **NONE**    | No DB involved, no encryption needed                              |

### ⚠️ CRITICAL: Session Data is ALWAYS Plaintext - NEVER Decrypt

**Session data has already been decrypted during login.** When you see code like:

```java
MemberVO member = (MemberVO) session.getAttribute("member");
String userName = member.getUserNm();  // This is ALREADY plaintext!
```

**DO NOT decrypt session data!** The decryption already happened when the user logged in (DB → Session flow).

| Pattern                                        | Action           | Reason                          |
| ---------------------------------------------- | ---------------- | ------------------------------- |
| `session.getAttribute(...)` → use data         | **NO DECRYPT**   | Session stores plaintext        |
| `session.getAttribute(...)` → save to DB       | **ENCRYPT only** | Plaintext → DB needs encryption |
| `session.getAttribute(...)` → return to client | **NO DECRYPT**   | Already plaintext               |

### Special Case: SELECT with WHERE clause on name columns

When `mapping_info` shows a name column in BOTH `input_mapping` AND `output_mapping` for a SELECT:

1. **First**: ENCRYPT the search parameter (to match encrypted data in DB)
2. **Then**: Execute the query
3. **Finally**: DECRYPT the result (to return plaintext to caller)

**How to identify this pattern:**
```json
{
  "command_type": "SELECT",
  "input_mapping": {
    "crypto_fields": [
      {"column_name": "emp_nm", "java_field": "searchName"}  // → ENCRYPT (WHERE clause)
    ]
  },
  "output_mapping": {
    "crypto_fields": [
      {"column_name": "emp_nm", "java_field": "empNm"}       // → DECRYPT (result)
    ]
  }
}
```

---

## Example Output

### Example: INSERT and SELECT with VO (Name fields only)

**mapping_info (from Phase 1):**
```json
{
  "queries": [
    {
      "query_id": "EmpMapper.insertEmp",
      "command_type": "INSERT",
      "sql_summary": "Employee registration - INSERT emp_nm",
      "input_mapping": {
        "type_category": "VO",
        "class_name": "EmpVO",
        "crypto_fields": [
          {"column_name": "emp_nm", "java_field": "empNm", "getter": "getEmpNm", "setter": "setEmpNm"}
        ]
      },
      "output_mapping": {
        "type_category": "NONE",
        "class_name": null,
        "crypto_fields": []
      }
    },
    {
      "query_id": "EmpMapper.selectEmp",
      "command_type": "SELECT",
      "sql_summary": "Employee retrieval - SELECT emp_nm",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "EmpVO",
        "crypto_fields": [
          {"column_name": "emp_nm", "java_field": "empNm", "getter": "getEmpNm", "setter": "setEmpNm"}
        ]
      }
    }
  ]
}
```

**Output:**

```json
{
  "data_flow_analysis": {
    "overview": "The employee table stores user name information. INSERT requires encryption before DB save, SELECT requires decryption after DB retrieval.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Employee Registration (INSERT)",
        "sql_query_id": "EmpMapper.insertEmp",
        "direction": "INBOUND_TO_DB",
        "data_source": {"type": "HTTP_REQUEST", "description": "Client POST request"},
        "data_sink": {"type": "DB", "description": "INSERT into TB_EMP"},
        "path": "Controller → Service.save() → DAO.insert() → DB",
        "sensitive_columns": ["emp_nm"]
      },
      {
        "flow_id": "FLOW_002",
        "flow_name": "Employee Retrieval (SELECT)",
        "sql_query_id": "EmpMapper.selectEmp",
        "direction": "DB_TO_OUTBOUND",
        "data_source": {"type": "DB", "description": "SELECT from TB_EMP"},
        "data_sink": {"type": "HTTP_RESPONSE", "description": "JSON response"},
        "path": "DB → DAO.select() → Service.get() → Controller → Client",
        "sensitive_columns": ["emp_nm"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "EmployeeService.java",
      "target_method": "saveEmployee",
      "action": "ENCRYPT",
      "reason": "FLOW_001: INSERT command requires encryption before DB save",
      "target_properties": ["empNm"],
      "insertion_point": "Right before employeeDao.insert(vo) call",
      "code_pattern_hint": "String empNmEncr = \"\";\nempNmEncr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed(vo.getEmpNm()),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm(), true),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nvo.setEmpNm(empNmEncr);"
    },
    {
      "flow_id": "FLOW_002",
      "file_name": "EmployeeService.java",
      "target_method": "getEmployeeById",
      "action": "DECRYPT",
      "reason": "FLOW_002: SELECT command requires decryption after DB retrieval",
      "target_properties": ["empNm"],
      "insertion_point": "Right after DAO return, before return statement",
      "code_pattern_hint": "String empNmDecr = \"\";\nempNmDecr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed(result.getEmpNm()),\n    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, result.getEmpNm(), true),\n    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nresult.setEmpNm(empNmDecr);"
    }
  ]
}
```

### Example: Map with Alias

**mapping_info shows:**
```json
{
  "output_mapping": {
    "type_category": "MAP",
    "class_name": "HashMap",
    "crypto_fields": [
      {"column_name": "emp_nm", "java_field": "name"}
    ]
  }
}
```

**code_pattern_hint for Map:**
```java
String nameDecr = "";
nameDecr = {{ common_util }}.getDefaultValue(
    !StringUtil.isEmptyTrimmed((String)resultMap.get("name")),
    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, (String)resultMap.get("name"), true),
    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, " ", true)
);
resultMap.put("name", nameDecr);
```

---

### Example: Empty crypto_fields (Phase 1 found no name columns) ★ CRITICAL

**Scenario:**
- SQL: `SELECT emp_id, dept_code FROM TB_EMP WHERE emp_id = #{empId}`
- Method chain: `EmpController.getDept()` → `EmpService.getDeptByEmpId()` → `EmpDao.selectDept()`
- Note: Phase 1 analyzed this query and found NO name columns (emp_nm not in SELECT)

**mapping_info from Phase 1:**
```json
{
  "query_id": "EmpMapper.selectDept",
  "command_type": "SELECT",
  "input_mapping": { "crypto_fields": [] },
  "output_mapping": { "crypto_fields": [] }
}
```

**Key Point:** Both `crypto_fields` are empty → **SKIP**. Do NOT invent encryption/decryption for columns not in Phase 1 result!

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Query retrieves non-sensitive columns (emp_id, dept_code). No name columns involved.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Get Department by EmpId",
        "sql_query_id": "EmpMapper.selectDept",
        "direction": "DB_TO_OUTBOUND",
        "data_source": {"type": "DB", "description": "SELECT non-sensitive columns"},
        "data_sink": {"type": "HTTP_RESPONSE", "description": "Return dept info"},
        "path": "EmpController → EmpService → EmpDao → DB",
        "sensitive_columns": []
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "EmpService.java",
      "target_method": "getDeptByEmpId",
      "action": "SKIP",
      "reason": "FLOW_001: Phase 1 crypto_fields is empty - query does not involve name columns",
      "target_properties": [],
      "insertion_point": "",
      "code_pattern_hint": ""
    }
  ]
}
```

---

### Example: SELECT with WHERE on name column + DECRYPT result

**Scenario:**
- SQL: `SELECT id, emp_nm FROM employee WHERE emp_nm = #{empNm}`
- Method chain: `SearchController.search()` → `EmployeeService.searchByName()` → `EmployeeDao.selectByName()`
- Note: WHERE clause uses encrypted column, results need decryption

**Key Point:** Must ENCRYPT search parameter first (to match encrypted DB data), then DECRYPT results.

**mapping_info shows:**
```json
{
  "input_mapping": {
    "type_category": "MAP",
    "class_name": "HashMap",
    "crypto_fields": [
      {"column_name": "emp_nm", "java_field": "empNm"}
    ]
  },
  "output_mapping": {
    "type_category": "VO",
    "class_name": "Employee",
    "crypto_fields": [
      {"column_name": "emp_nm", "java_field": "empNm", "getter": "getEmpNm", "setter": "setEmpNm"}
    ]
  }
}
```

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Search by name requires encrypting the search parameter to match encrypted DB data, then decrypting results for display.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Employee Search with Encrypted WHERE",
        "sql_query_id": "EmployeeMapper.selectByName",
        "direction": "BIDIRECTIONAL",
        "INBOUND_TO_DB": {
          "data_source": {"type": "HTTP_REQUEST", "description": "Search parameter (name) from user input"},
          "data_sink": {"type": "DB", "description": "Query executes against encrypted DB data"}
        },
        "DB_TO_OUTBOUND": {
          "data_source": {"type": "DB", "description": "Encrypted results from database"},
          "data_sink": {"type": "HTTP_RESPONSE", "description": "Decrypted results returned to client"}
        },
        "path": "SearchController → EmployeeService.searchByName() → DAO → DB → Service → Controller → Client",
        "sensitive_columns": ["emp_nm"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "EmployeeService.java",
      "target_method": "searchByName",
      "action": "ENCRYPT_THEN_DECRYPT",
      "reason": "FLOW_001: BIDIRECTIONAL - search param needs ENCRYPT, results need DECRYPT",
      "target_properties": ["empNm"],
      "insertion_point": "ENCRYPT: Before employeeDao.selectByName() call; DECRYPT: After DAO return",
      "code_pattern_hint": "// Before DAO call: encrypt search parameter\nString empNmEncr = \"\";\nempNmEncr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed((String)searchParam.get(\"empNm\")),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, (String)searchParam.get(\"empNm\"), true),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nsearchParam.put(\"empNm\", empNmEncr);\nList<Employee> resultList = employeeDao.selectByName(searchParam);\n// After DAO call: decrypt results\nfor (Employee e : resultList) {\n    String empNmDecr = {{ common_util }}.getDefaultValue(\n        !StringUtil.isEmptyTrimmed(e.getEmpNm()),\n        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, e.getEmpNm(), true),\n        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, \" \", true)\n    );\n    e.setEmpNm(empNmDecr);\n}"
    }
  ]
}
```

---

## Start Analysis Now

Based on the information above:

1. **For each call chain in call_stacks**, find the matching query in mapping_info
2. **Check `crypto_fields` first** - if BOTH input_mapping AND output_mapping have empty crypto_fields → `action: "SKIP"`
3. **Use `command_type`** and mapping location to determine ENCRYPT/DECRYPT action
4. **Use `java_field`, `getter`, `setter`** from crypto_fields to generate accurate code patterns
5. **Output modification instructions** for each flow in JSON format
6. **Always use `SliEncryptionConstants.Policy.NAME`** for all name fields

**★★★ CRITICAL REMINDER ★★★**
- **Trust Phase 1 results**: If `crypto_fields` is empty, the query does NOT need encryption/decryption
- **DO NOT invent fields**: Only use fields explicitly listed in `crypto_fields`
- **SKIP when appropriate**: Empty `crypto_fields` means `action: "SKIP"`
- **NAME ONLY**: This template only processes name fields with `SliEncryptionConstants.Policy.NAME`

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`. No other text allowed.**
