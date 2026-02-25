# Encryption/Decryption Modification Planning (Phase 2) - CCS Version (Name Only)

## Role

You are an expert in analyzing **Data Flow** in Java Spring Boot legacy systems.
Based on the information below, output specific modification instructions in JSON format describing **where**, **what**, and **how** to insert encryption/decryption logic.

**Important**: Your role is **analysis and planning**. Actual code writing will be done in the next step.

---

## ★ SCOPE: NAME Fields Only ★

**This template processes ONLY `column_type: "name"` fields.**

| Rule             | Description                                                                 |
| ---------------- | --------------------------------------------------------------------------- |
| **Policy**       | Always use `SliEncryptionConstants.Policy.NAME`                             |
| **Scope**        | Ignore other sensitive data types (DOB, RRN, TEL_NO, etc.)                  |
| **Preservation** | All existing encryption for other fields MUST remain unchanged              |
| **Addition**     | Only add new NAME-specific crypto logic; do NOT modify existing crypto code |

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

| Field Type      | column_type | Policy Constant                      | Column Name Patterns                                                                                  |
| --------------- | ----------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Name (이름)** | `name`      | `SliEncryptionConstants.Policy.NAME` | name, userName, user_name, fullName, firstName, lastName, custNm, CUST_NM, empNm, EMP_NM, gvnm, aenam |

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

## CCS Utility Classes (★ for CCS Projects)

This project uses CCS-specific utility classes for encryption/decryption wrappers with null-safety.

### Configured Utility Classes

{{ ccs_util_info }}

### Single-Record Encryption Pattern (★ CRITICAL: Null-safe wrapper)

**For ENCRYPT action - Use `{{ common_util }}.getDefaultValue()` wrapper:**

```java
// AI 암호화 적용
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
// AI 암호화 적용
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
// AI 암호화 적용
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
// AI 암호화 적용
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

| Scenario                                                  | Pattern                              | Action         | Priority | Note                                 |
| --------------------------------------------------------- | ------------------------------------ | -------------- | -------- | ------------------------------------ |
| Single VO encryption                                      | Single-Record Encryption             | `ENCRYPT`      | -        | Single VO encryption                 |
| Single VO decryption                                      | Single-Record Decryption             | `DECRYPT`      | -        | Single VO decryption                 |
| **★ Existing for-loop decrypting other sensitive fields** | **Single-Record inside existing loop** | **`DECRYPT`** | **1st**  | **Reuse existing loop (HIGHEST)**    |
| List<VO> decryption (with masking)                        | setListDecryptAndMask + mask loop    | `DECRYPT_LIST` | 2nd      | Batch decrypt + masking              |
| List<VO> decryption (no masking)                          | setListDecryptAndMask(..., false)    | `DECRYPT_LIST` | 2nd      | Batch decrypt, no masking            |

**★★★ Decision rule for List decryption (MUST follow this priority) ★★★:**

1. **FIRST (HIGHEST PRIORITY)**: Check if existing code already has a for-loop that:
   - **Iterates over the SAME VO that contains the NAME field** (this is critical!)
   - Decrypts OTHER sensitive data (RRN/jumin, phone, email, etc.) in that VO
   - If YES → Add NAME decryption inside the existing for-loop → `action: "DECRYPT"`
   - This maintains code consistency and avoids duplicate loops
2. **SECOND**: If no existing decrypt for-loop for the SAME VO exists → Use Multi-Record pattern
   - If masking needed → `setListDecryptAndMask` + mask loop → `action: "DECRYPT_LIST"`
   - If no masking → `setListDecryptAndMask(..., false)` → `action: "DECRYPT_LIST"`

**⚠️ IMPORTANT: The for-loop MUST iterate over the SAME VO type that contains the NAME field!**
- ✅ Correct: `for (EmployeeVO vo : employeeList)` where `EmployeeVO` has `empNm` field
- ❌ Wrong: Using a for-loop that iterates over a DIFFERENT VO type

### ★★★ CRITICAL: Existing For-Loop Detection Guidelines ★★★

**IMPORTANT: Before deciding on DECRYPT_LIST action, you MUST first check if an existing for-loop exists!**

When you need to decrypt a `List<VO>`, analyze the source code to determine if there is **already a for-loop that iterates over the SAME VO containing the NAME field AND decrypts other sensitive data (RRN/jumin, phone, email, etc.)** using single-record pattern.

**⚠️ KEY CONDITION: The for-loop MUST iterate over the SAME VO type that contains the NAME field!**

**Detection Rules:**

| Existing Code Pattern                                                              | Detection Signal                              | Recommended Action                       |
| ---------------------------------------------------------------------------------- | --------------------------------------------- | ---------------------------------------- |
| `for (EmployeeVO vo : empList) { decrypt(juminNo)... }` where EmployeeVO has empNm | Loop iterates SAME VO + decrypts other fields | Add NAME decrypt inside loop → `DECRYPT` |
| `for (int i = 0; i < list.size(); i++) { list.get(i).getJuminNo()... }`            | Same VO list + decrypts other fields          | Add NAME decrypt inside loop → `DECRYPT` |
| For-loop iterates over a DIFFERENT VO type                                         | Different VO - not applicable                 | Use `setListDecryptAndMask` → `DECRYPT_LIST` |
| No decrypt loop exists for the target VO                                           | No existing decrypt pattern                   | Use `setListDecryptAndMask` → `DECRYPT_LIST` |

**Example - When existing for-loop EXISTS (iterating the SAME VO with NAME field):**

```java
// Existing code already has a for-loop decrypting RRN and phone number
// NOTE: outSVOs is the SAME VO type that contains the NAME field (empNm)
for (int i = 0; i < outSVOs.size(); i++) {
    // Existing RRN decryption
    String juminDecr = {{ common_util }}.getDefaultValue(
        !StringUtil.isEmptyTrimmed(outSVOs.get(i).getJuminNo()),
        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.RRN, outSVOs.get(i).getJuminNo(), true),
        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.RRN, " ", true)
    );
    outSVOs.get(i).setJuminNo(juminDecr);

    // Existing phone number decryption
    String telDecr = {{ common_util }}.getDefaultValue(
        !StringUtil.isEmptyTrimmed(outSVOs.get(i).getTelNo()),
        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.TEL_NO, outSVOs.get(i).getTelNo(), true),
        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.TEL_NO, " ", true)
    );
    outSVOs.get(i).setTelNo(telDecr);

    // ★ ADD NAME decryption code HERE! (DO NOT create a new loop)
}
```

→ For this case, use `action: "DECRYPT"` and set `insertion_point` to "Inside existing for-loop, after other decrypt operations".

**Decision Flow:**

```
List<VO> decryption needed? (VO contains NAME field)
    │
    ▼
Does existing code have a for-loop iterating over the SAME VO?
    │
    ├── YES: Does this for-loop decrypt OTHER sensitive data (jumin/tel/email) of the SAME VO?
    │         │
    │         ├── YES → action: "DECRYPT"
    │         │         insertion_point: "Inside existing for-loop, after other decrypt code"
    │         │
    │         └── NO → For-loop is for business logic, not decryption
    │                   → action: "DECRYPT_LIST"
    │
    └── NO (or for-loop iterates DIFFERENT VO) → action: "DECRYPT_LIST"
```

---

## Analysis Target Information

### Target Table/Column Information

(See "Role of table_info vs mapping_info" section above for detailed explanation)

{{ table_info }}

**Quick Reference:**

- Use `mapping_info.crypto_fields` as the source of truth (analyzed in Phase 1)
- If `crypto_fields` is empty → `action: "SKIP"`
- Only generate instructions for files in `source_files` and methods in `call_stacks`

### Data Mapping Summary (★ Pre-analyzed from Phase 1)

The following `mapping_info` was extracted in Phase 1 and contains all SQL query analysis results.

**★★★ CRITICAL: Trust Phase 1 Results ★★★**

**IMPORTANT: If a query appears in `mapping_info`, it HAS ALREADY BEEN VERIFIED to access the target table.**

- Phase 1 analyzed ALL SQL queries and filtered ONLY those accessing the target table
- Do NOT re-evaluate whether a query accesses the target table
- The target table may be accessed via subquery, JOIN, or other complex SQL patterns
- If `crypto_fields` is non-empty, encryption/decryption IS required - trust this analysis

**Field Presence Rules:**

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
            "java_field": "Java field name or Map key"
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

| Field           | Description                        | How to Use                                                                                                                    |
| --------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `query_id`      | Matches DAO/Mapper method name     | Match with call chain to identify which query is called                                                                       |
| `command_type`  | SQL command type                   | `SELECT` → DECRYPT results, `INSERT/UPDATE` → ENCRYPT inputs                                                                  |
| `sql_summary`   | Query purpose description          | Understand what the query does                                                                                                |
| `crypto_fields` | Array of fields needing encryption | Contains `column_name` and `java_field`                                                                                       |
| `java_field`    | Field name (VO) or Map key         | For VO: infer getter/setter (e.g., `empNm` → `getEmpNm()`, `setEmpNm()`). For Map: use as key (e.g., `map.get("java_field")`) |

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

### DQM Interface (★ XML Query → Java Method Mapping)

The following DQM.java files show how XML queries are mapped to Java methods.
**Use this to understand which Java method calls which SQL query.**

**Key Pattern in CCS:**

- XML query id: `namespace-methodName` (e.g., `com.example.dqm-selectUser`)
- DQM.java method: `methodName(...)` internally calls `selectList("namespace-methodName", param)` or similar

**How to use:**

1. Find the DQM method called in SVCImpl (e.g., `userDQM.selectUser(vo)`)
2. Look at the DQM.java code below to see which XML query id it calls
3. Match that query id with `mapping_info.queries[].query_id`
4. Use `mapping_info.crypto_fields` to determine encryption/decryption needs

{{ dqm_java_info }}

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
4. **★ For List<VO> SELECT result decryption, ALWAYS analyze source code for existing for-loop:**
   - Search method body for `for (int i = 0; ...)` or `for (VO vo : list)` patterns
   - Check if the for-loop contains **decrypt code for OTHER sensitive data (RRN/jumin, phone, email, etc.)**
   - If existing decrypt for-loop found → `action: "DECRYPT"` (add NAME decrypt inside existing loop)
   - If no existing for-loop → `action: "DECRYPT_LIST"` (use setListDecryptAndMask)
5. All name fields use `SliEncryptionConstants.Policy.NAME`.

### 2. Using Data Mapping (from mapping_info)

**Refer to the code patterns in "CCS Utility Classes" section above.**

Use the following rules to apply the patterns:

| Type          | Rule                                                                | Example                                             |
| ------------- | ------------------------------------------------------------------- | --------------------------------------------------- |
| **VO**        | Infer getter/setter from `java_field` using JavaBean conventions    | `java_field: "empNm"` → `getEmpNm()` / `setEmpNm()` |
| **Map**       | Use `java_field` as the Map key (includes aliases if SQL uses them) | `map.get("name")` / `map.put("name", ...)`          |
| **Primitive** | Apply pattern directly to the variable                              | `empNm = empNmEncr;`                                |

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

### 5. SliVOUtil.copy Pattern Analysis (★★★ CRITICAL for CCS ★★★)

**Pattern Description:**
CCS projects often use `SliVOUtil.copy(source, target)` to transfer data between VO layers:

- **BVO (Biz VO)**: Used in Biz layer
- **SVO (Service VO)**: Used in Service layer

**⚠️ CRITICAL: Determine correct VO for encryption/decryption**

When you see `SliVOUtil.copy(bvo, svo)` followed by `return svo`:

- The **returned/passed VO** is what matters for crypto operations
- You must apply crypto to the VO that will actually be used downstream

**Valid Decryption Placements:**

```java
// Option 1: Decrypt bvo BEFORE copy (bvo's decrypted value gets copied to svo)
String userNmDecr = {{ common_util }}.getDefaultValue(...);
bvo.setUserNm(userNmDecr);
SliVOUtil.copy(bvo, svo);  // svo now has decrypted value
return svo;

// Option 2: Decrypt svo AFTER copy
SliVOUtil.copy(bvo, svo);  // svo has encrypted value
String userNmDecr = {{ common_util }}.getDefaultValue(...);
svo.setUserNm(userNmDecr);  // decrypt directly on svo
return svo;
```

**❌ INVALID Placement (DO NOT DO THIS):**

```java
SliVOUtil.copy(bvo, svo);  // copy already done
String userNmDecr = {{ common_util }}.getDefaultValue(...);
bvo.setUserNm(userNmDecr);  // USELESS! svo is unchanged, bvo is discarded
return svo;  // svo still has encrypted value!
```

**Decision Rules:**

| Pattern                       | Recommended Crypto Location | insertion_point                         |
| ----------------------------- | --------------------------- | --------------------------------------- |
| `copy(bvo, svo); return svo;` | copy 후 svo에 적용          | "Right after SliVOUtil.copy(), on svo"  |
| `copy(bvo, svo); return svo;` | 또는 copy 전 bvo에 적용     | "Right before SliVOUtil.copy(), on bvo" |
| `return bvo;` (copy 없음)     | bvo에 적용                  | Standard placement                      |

**How to identify which VO to modify:**

1. Find `SliVOUtil.copy(source, target)` calls in the method
2. Trace which VO is returned or passed to next method
3. Apply crypto either:
   - **Before copy**: on `source` VO
   - **After copy**: on `target` VO (the one being returned/used)
4. **NEVER** apply crypto on source VO after copy - it has no effect

---

## Output Format (★ JSON ONLY)

**IMPORTANT OUTPUT RULES:**

1. Output **ONLY** valid JSON - no explanations, no markdown, no comments before or after
2. Do **NOT** include `json or ` markers
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

| Field               | Description                                      | Example                                                                                      |
| ------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `flow_id`           | Reference to data_flow_analysis.flows[].flow_id  | `FLOW_001`, `FLOW_002`                                                                       |
| `sql_query_id`      | Matching query_id from mapping_info.queries[]    | `com.example.mapper.UserMapper.insertUser`                                                   |
| `file_name`         | File name to modify (**empty string `""` if action is SKIP**) | `UserService.java`, `EmpController.java`, or `""` for SKIP                                   |
| `target_method`     | Method name to modify (**empty string `""` if action is SKIP**) | `saveUser`, `getUserList`, or `""` for SKIP                                                  |
| `action`            | Action to perform                                | `ENCRYPT`, `DECRYPT`, `DECRYPT_LIST`, `ENCRYPT_THEN_DECRYPT`, `SKIP`                         |
| `target_properties` | Properties to encrypt/decrypt (array of strings) | `["empNm", "custNm"]`                                                                        |
| `insertion_point`   | **Specific** code location with actual code references | `After 'EmployeeVO result = empDao.selectById(id);' and before 'return result;'`             |
| `code_pattern_hint` | Code pattern example (must start with `// AI 암호화 적용`) | `// AI 암호화 적용\nString empNmEncr = ...` |

### ⚠️ CRITICAL: Every Flow MUST Have a modification_instruction Entry ⚠️

**For EVERY flow in `data_flow_analysis.flows`, you MUST output a corresponding entry in `modification_instructions`.**

- If the flow requires encryption/decryption → output with `action: "ENCRYPT"` or `action: "DECRYPT"`
- If the flow does NOT require modification → output with `action: "SKIP"` and explain `reason`

**DO NOT skip any flow!** The Execution phase relies on explicit SKIP entries to know which flows were analyzed and intentionally skipped.

**Example:** If `data_flow_analysis.flows` contains FLOW_001, FLOW_002, FLOW_003, then `modification_instructions` MUST contain entries for ALL three flows (even if some are SKIP).

### Important Notes

1. **sql_query_id**: Copy the exact `query_id` from `mapping_info.queries[]` that corresponds to this flow. Match the DAO method in `call_stacks` with `query_id` in `mapping_info`. If no DB access (e.g., Session → HTTP_RESPONSE), use `null`.
2. **When action is SKIP**:
   - Set `file_name` to empty string `""`
   - Set `target_method` to empty string `""`
   - Set `target_properties` to empty array `[]`
   - Set `insertion_point` to empty string `""`
   - Set `code_pattern_hint` to empty string `""`
   - Specify in `reason` which flow (flow_id) this refers to and why no modification is needed
3. **target_properties**: Array of `java_field` names (strings) from `crypto_fields`. Use the Java field name, not DB column name.
4. **insertion_point**: **MUST be highly specific** with actual code references from source files:
   - **Format**: `After '<actual_code_line>' and before '<actual_code_line>'`
   - **Quote actual code**: Include variable names, method calls, and statements from the source file
   - **Bad example** ❌: `"Right after DAO return, before return statement"` (too vague)
   - **Good example** ✅: `"After 'List<EmpBVO> bvoList = empDQM.selectEmpList(param);' and before 'return bvoList;'"`
   - **Good example** ✅: `"After 'bvo.setTelNo(telDecr);' inside the existing for-loop, before 'SliVOUtil.copy(bvo, svo);'"`
   - **For ENCRYPT_THEN_DECRYPT**: Specify both locations clearly with actual code
     - Example: `"ENCRYPT: After 'String searchName = param.getSearchName();' and before 'List<EmpVO> results = empDao.selectByName(param);' | DECRYPT: After the DAO call and before 'return results;'"`
5. **code_pattern_hint**:
   - For VO: Infer getter/setter from `java_field` (e.g., `java_field: "empNm"` → `vo.getEmpNm()`, `vo.setEmpNm(...)`)
   - For Map: Use `java_field` as key (e.g., `map.put("name", SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, (String)map.get("name")));`)
6. **Use mapping_info.crypto_fields**: Reference `java_field` for accurate code patterns (infer getter/setter using JavaBean conventions)
7. **Always use `SliEncryptionConstants.Policy.NAME`** for all encryption/decryption operations
8. **"// AI 암호화 적용" Comment**: Every `code_pattern_hint` MUST start with `// AI 암호화 적용` comment
   - This comment marks AI-modified code for later review
   - Add once per modification_instruction, at the beginning of the code block

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
      { "column_name": "emp_nm", "java_field": "searchName" } // → ENCRYPT (WHERE clause)
    ]
  },
  "output_mapping": {
    "crypto_fields": [
      { "column_name": "emp_nm", "java_field": "empNm" } // → DECRYPT (result)
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
        "crypto_fields": [{ "column_name": "emp_nm", "java_field": "empNm" }]
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
        "crypto_fields": [{ "column_name": "emp_nm", "java_field": "empNm" }]
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
        "data_source": {
          "type": "HTTP_REQUEST",
          "description": "Client POST request"
        },
        "data_sink": { "type": "DB", "description": "INSERT into TB_EMP" },
        "path": "Controller → Service.save() → DAO.insert() → DB",
        "sensitive_columns": ["emp_nm"]
      },
      {
        "flow_id": "FLOW_002",
        "flow_name": "Employee Retrieval (SELECT)",
        "sql_query_id": "EmpMapper.selectEmp",
        "direction": "DB_TO_OUTBOUND",
        "data_source": { "type": "DB", "description": "SELECT from TB_EMP" },
        "data_sink": {
          "type": "HTTP_RESPONSE",
          "description": "JSON response"
        },
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
      "insertion_point": "After 'vo.setDeptCode(param.getDeptCode());' and right before 'employeeDao.insert(vo);'",
      "code_pattern_hint": "// AI 암호화 적용\nString empNmEncr = \"\";\nempNmEncr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed(vo.getEmpNm()),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm(), true),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nvo.setEmpNm(empNmEncr);"
    },
    {
      "flow_id": "FLOW_002",
      "file_name": "EmployeeService.java",
      "target_method": "getEmployeeById",
      "action": "DECRYPT",
      "reason": "FLOW_002: SELECT command requires decryption after DB retrieval",
      "target_properties": ["empNm"],
      "insertion_point": "After 'EmployeeVO result = employeeDao.selectById(id);' and before 'return result;'",
      "code_pattern_hint": "// AI 암호화 적용\nString empNmDecr = \"\";\nempNmDecr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed(result.getEmpNm()),\n    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, result.getEmpNm(), true),\n    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nresult.setEmpNm(empNmDecr);"
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
    "crypto_fields": [{ "column_name": "emp_nm", "java_field": "name" }]
  }
}
```

**code_pattern_hint for Map:**

```java
// AI 암호화 적용
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
        "data_source": {
          "type": "DB",
          "description": "SELECT non-sensitive columns"
        },
        "data_sink": {
          "type": "HTTP_RESPONSE",
          "description": "Return dept info"
        },
        "path": "EmpController → EmpService → EmpDao → DB",
        "sensitive_columns": []
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "",
      "target_method": "",
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

### Example: List Decryption WITH Existing For-Loop (★ CRITICAL Pattern)

**Scenario:**

- SQL: `SELECT emp_id, emp_nm, jumin_no, tel_no FROM employee`
- Method chain: `EmployeeController.list()` → `EmployeeService.getList()` → `EmployeeDao.selectList()`
- **Key Point:** Source code ALREADY has a for-loop decrypting jumin_no and tel_no **in the SAME VO (EmployeeBVO) that contains emp_nm**

**Existing source code in EmployeeService.java:**

```java
public List<EmployeeSVO> getList(EmployeeBVO param) {
    List<EmployeeBVO> bvoList = employeeDao.selectList(param);
    List<EmployeeSVO> svoList = new ArrayList<>();

    for (int i = 0; i < bvoList.size(); i++) {
        EmployeeBVO bvo = bvoList.get(i);
        EmployeeSVO svo = new EmployeeSVO();

        // Existing RRN decryption
        String juminDecr = {{ common_util }}.getDefaultValue(
            !StringUtil.isEmptyTrimmed(bvo.getJuminNo()),
            SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.RRN, bvo.getJuminNo(), true),
            SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.RRN, " ", true)
        );
        bvo.setJuminNo(juminDecr);

        // Existing phone number decryption
        String telDecr = {{ common_util }}.getDefaultValue(
            !StringUtil.isEmptyTrimmed(bvo.getTelNo()),
            SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.TEL_NO, bvo.getTelNo(), true),
            SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.TEL_NO, " ", true)
        );
        bvo.setTelNo(telDecr);

        SliVOUtil.copy(bvo, svo);
        svoList.add(svo);
    }
    return svoList;
}
```

**Analysis:** Existing for-loop ALREADY decrypts jumin_no and tel_no. Add NAME decrypt to the SAME loop!

**Correct Output:**

```json
{
  "data_flow_analysis": {
    "overview": "Employee list retrieval. Existing code has for-loop decrypting jumin_no/tel_no. Name decryption should be added to the same loop.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Employee List Retrieval",
        "sql_query_id": "EmployeeMapper.selectList",
        "direction": "DB_TO_OUTBOUND",
        "data_source": { "type": "DB", "description": "SELECT from employee table" },
        "data_sink": { "type": "HTTP_RESPONSE", "description": "Return employee list" },
        "path": "EmployeeController → EmployeeService.getList() → EmployeeDao → DB",
        "sensitive_columns": ["emp_nm"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "EmployeeService.java",
      "target_method": "getList",
      "action": "DECRYPT",
      "reason": "FLOW_001: Existing for-loop already decrypts juminNo and telNo. Add NAME decrypt to the same loop for consistency.",
      "target_properties": ["empNm"],
      "insertion_point": "Inside existing for-loop, after telNo decryption and before SliVOUtil.copy(bvo, svo)",
      "code_pattern_hint": "// AI 암호화 적용\nString empNmDecr = \"\";\nempNmDecr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed(bvo.getEmpNm()),\n    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, bvo.getEmpNm(), true),\n    SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nbvo.setEmpNm(empNmDecr);"
    }
  ]
}
```

**WRONG approach (DO NOT DO THIS):**

```json
{
  "action": "DECRYPT_LIST",
  "code_pattern_hint": "Map<String, String> targetEncr = new HashMap<>();\ntargetEncr.put(\"empNm\", SliEncryptionConstants.Policy.NAME);\nbvoList = {{ common_util }}.setListDecryptAndMask(bvoList, targetEncr);"
}
```

This would create a DUPLICATE decrypt pattern and potentially cause issues with the existing for-loop logic.

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
    "crypto_fields": [{ "column_name": "emp_nm", "java_field": "empNm" }]
  },
  "output_mapping": {
    "type_category": "VO",
    "class_name": "Employee",
    "crypto_fields": [{ "column_name": "emp_nm", "java_field": "empNm" }]
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
      "insertion_point": "ENCRYPT: After 'Map<String, Object> searchParam = new HashMap<>();' and before 'List<Employee> resultList = employeeDao.selectByName(searchParam);' | DECRYPT: After the DAO call 'List<Employee> resultList = employeeDao.selectByName(searchParam);' and before 'return resultList;'",
      "code_pattern_hint": "// AI 암호화 적용\n// Before DAO call: encrypt search parameter\nString empNmEncr = \"\";\nempNmEncr = {{ common_util }}.getDefaultValue(\n    !StringUtil.isEmptyTrimmed((String)searchParam.get(\"empNm\")),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, (String)searchParam.get(\"empNm\"), true),\n    SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, \" \", true)\n);\nsearchParam.put(\"empNm\", empNmEncr);\nList<Employee> resultList = employeeDao.selectByName(searchParam);\n// After DAO call: decrypt results\nfor (Employee e : resultList) {\n    String empNmDecr = {{ common_util }}.getDefaultValue(\n        !StringUtil.isEmptyTrimmed(e.getEmpNm()),\n        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, e.getEmpNm(), true),\n        SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, \" \", true)\n    );\n    e.setEmpNm(empNmDecr);\n}"
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
4. **Use `java_field`** from crypto_fields to generate accurate code patterns (infer getter/setter from java_field)
5. **Output modification instructions** for each flow in JSON format
6. **Always use `SliEncryptionConstants.Policy.NAME`** for all name fields

**★★★ CRITICAL REMINDER ★★★**

- **Trust Phase 1 results**: If `crypto_fields` is empty, the query does NOT need encryption/decryption
- **DO NOT invent fields**: Only use fields explicitly listed in `crypto_fields`
- **SKIP when appropriate**: Empty `crypto_fields` means `action: "SKIP"`
- **NAME ONLY**: This template only processes name fields with `SliEncryptionConstants.Policy.NAME`

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`. No other text allowed.**
