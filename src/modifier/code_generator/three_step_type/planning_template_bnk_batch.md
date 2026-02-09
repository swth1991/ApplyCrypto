# Encryption/Decryption Modification Planning (Phase 2) - BNK Batch Version

## Role

You are an expert in analyzing **Data Flow** in Java Batch programs.
Based on the information below, output specific modification instructions in JSON format describing **where**, **what**, and **how** to insert encryption/decryption logic.

**Important**: Your role is **analysis and planning**. Actual code writing will be done in the next step.

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

### Policy ID Determination (★★★ CRITICAL ★★★)

**IMPORTANT: Use the following priority order to determine the correct policy constant:**

1. **FIRST**: Check `table_info.columns[].encryption_code` - If provided, use it directly
2. **SECOND**: Check `table_info.columns[].column_type` and map to policy constant:
   - `column_type: "name"` → `SliEncryptionConstants.Policy.NAME`
   - `column_type: "dob"` → `SliEncryptionConstants.Policy.DOB`
   - `column_type: "rrn"` → `SliEncryptionConstants.Policy.ENC_NO`
3. **FALLBACK**: If neither is provided, use column name pattern matching (see table below)

### Policy Constant Reference Table

| Field Type                     | column_type | Policy Constant                          | Column Name Patterns (fallback only)                                                     |
| ------------------------------ | ----------- | ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Name (이름)**                | `name`      | `SliEncryptionConstants.Policy.NAME`     | name, userName, user_name, fullName, firstName, lastName, custNm, CUST_NM, empNm, EMP_NM |
| **Date of Birth (생년월일)**   | `dob`       | `SliEncryptionConstants.Policy.DOB`      | dob, dateOfBirth, birthDate, birthday, dayOfBirth, birthDt, BIRTH_DT                     |
| **Resident Number (주민등록번호)** | `rrn`   | `SliEncryptionConstants.Policy.ENC_NO`   | jumin, juminNumber, ssn, residentNumber, juminNo, JUMIN_NO, residentNo, rrn              |

### ★★★ CRITICAL: Role of table_info vs mapping_info ★★★

**`table_info.columns`**: Project-level configuration - columns that MAY need encryption/decryption
- Used to determine the correct `policy constant` (via `encryption_code` or `column_type`)
- Does NOT mean every query must encrypt/decrypt these columns

**`mapping_info.crypto_fields`**: Query-level analysis result from Phase 1 - columns that ACTUALLY need encryption/decryption for each specific query
- **THIS IS THE SOURCE OF TRUTH** for what to encrypt/decrypt
- If `crypto_fields` is empty for a query → that query does NOT need encryption/decryption for this table

**⚠️ DO NOT INVENT crypto_fields!** If Phase 1 returned empty `crypto_fields` for a query, trust it. Do NOT add fields just because they exist in `table_info.columns`.

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
- `column_type`: Type of sensitive data - `"name"`, `"dob"`, or `"rrn"` (optional but authoritative)
- `encryption_code`: Direct policy constant to use - e.g., `"SliEncryptionConstants.Policy.NAME"` (optional but highest priority)

**Instructions:**

1. **Trust `mapping_info.crypto_fields`** - this is Phase 1's analysis result. If it's empty, NO encryption/decryption needed for that query
2. Use `table_info.columns[]` to look up `encryption_code` or `column_type` for determining policy constant
3. Analyze queries from `mapping_info.queries[]` (NOT raw SQL - SQL was analyzed in Phase 1)
4. Generate modification instructions for the BAT.java file
5. **If `crypto_fields` is empty** → output `action: "SKIP"` with `target_method: ""` and `file_name: ""`

### Data Mapping Summary (★ Pre-analyzed from Phase 1)

The following `mapping_info` was extracted in Phase 1 and contains all SQL query analysis results, including SQL ID to VO class mappings.

**★★★ CRITICAL: Trust Phase 1 Results ★★★**

**IMPORTANT: If a query appears in `mapping_info`, it HAS ALREADY BEEN VERIFIED to access the target table.**

- Phase 1 analyzed ALL SQL queries and filtered ONLY those accessing the target table
- Do NOT re-evaluate whether a query accesses the target table
- The target table may be accessed via subquery, JOIN, or other complex SQL patterns
- If `crypto_fields` is non-empty, encryption/decryption IS required - trust this analysis

**Field Presence Rules:**
- If `input_mapping.crypto_fields` is empty → NO encryption needed for input
- If `output_mapping.crypto_fields` is empty → NO decryption needed for output
- If BOTH are empty → `action: "SKIP"` with `target_method: ""` and `file_name: ""`
- **DO NOT invent or add fields** that weren't identified in Phase 1

**mapping_info Structure for BNK Batch:**

```json
{
  "queries": [
    {
      "query_id": "sel04",
      "command_type": "SELECT | INSERT | UPDATE | DELETE",
      "sql_summary": "Brief description of query purpose",
      "input_mapping": {
        "type_category": "VO | MAP | PRIMITIVE | NONE",
        "class_name": "XXXBatVO",
        "crypto_fields": [
          {
            "column_name": "DB column name",
            "java_field": "Java field name",
            "getter": "getXxx",
            "setter": "setXxx"
          }
        ]
      },
      "output_mapping": {
        "type_category": "VO | MAP | PRIMITIVE | NONE",
        "class_name": "XXXBatVO",
        "crypto_fields": [...]
      }
    }
  ]
}
```

**Key Fields to Use:**

| Field | Description | How to Use |
|-------|-------------|------------|
| `query_id` | SQL query ID from XML | Match with itemFactory.getItemReader/getItemWriter calls |
| `command_type` | SQL command type | `SELECT` → DECRYPT results, `INSERT/UPDATE` → ENCRYPT inputs |
| `crypto_fields` | Array of fields needing encryption | Contains `column_name`, `java_field`, `getter/setter` |
| `getter/setter` | VO methods | Use directly in code_pattern_hint |

**Determining ENCRYPT/DECRYPT action:**

- `SELECT` with `output_mapping.crypto_fields` → DECRYPT after `itemReader.read()` returns
- `INSERT/UPDATE` with `input_mapping.crypto_fields` → ENCRYPT before `itemWriter.write()` call

{{ mapping_info }}

{% if dqm_java_info %}
### DQM Interface (XML Query → Java Method Mapping)

The following files show how XML queries are mapped to Java methods.
**Use this to understand which Java method calls which SQL query.**

{{ dqm_java_info }}
{% endif %}

### Source Files to Modify

{{ source_files }}

---

## Analysis Guidelines for Batch Programs

### 1. Data Flow Analysis in BAT.java

**Batch programs have a simpler flow than web applications:**

1. **Find ItemReader usage** - `itemFactory.getItemReader("sqlId", VO.class)`
   - This is SELECT from DB
   - After `read()`, VO contains encrypted data → DECRYPT needed

2. **Find ItemWriter usage** - `itemFactory.getItemWriter("sqlId")`
   - This is INSERT/UPDATE to DB
   - Before `write()`, VO data needs → ENCRYPT needed

3. **Analyze data flow between VOs**:
   ```java
   // Pattern: Read → Process → Write
   SourceVO srcVo = reader.read();        // SELECT: needs DECRYPT
   TargetVO tgtVo = new TargetVO();
   tgtVo.setCustNm(srcVo.getCustNm());    // Data transfer
   writer.write(tgtVo);                    // INSERT: needs ENCRYPT
   ```

### 2. Common Batch Patterns

**Pattern 1: Simple Read → Write**
```java
while (reader.next()) {
    SrcVO vo = reader.read();
    // Decrypt after read
    vo.setCustNm(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, vo.getCustNm()));

    TgtVO tgt = new TgtVO();
    tgt.setCustNm(vo.getCustNm());  // Already decrypted

    // Encrypt before write
    tgt.setCustNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, tgt.getCustNm()));
    writer.write(tgt);
}
```

**Pattern 2: Read Only (Report/Export)**
```java
while (reader.next()) {
    ReportVO vo = reader.read();
    // Decrypt for display/export
    vo.setEmpNm(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, vo.getEmpNm()));
    reportWriter.write(vo);  // To file, not DB
}
```

**Pattern 3: Write Only (Import)**
```java
while (fileReader.hasNext()) {
    ImportVO vo = parseFromFile();
    // Encrypt before DB write
    vo.setRrnEncr(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.ENC_NO, vo.getRrnEncr()));
    dbWriter.write(vo);
}
```

### 3. Where to Insert Crypto Code

**For DECRYPT (after SELECT):**
- Insert immediately after `ItemReader.read()` returns
- Process the VO before any business logic uses the data

**For ENCRYPT (before INSERT/UPDATE):**
- Insert immediately before `ItemWriter.write()` call
- After all business logic has finished populating the VO

### 4. Using getter/setter from mapping_info

**With `getter`/`setter` provided (from BATVO analysis):**
```java
vo.setCustNm(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, vo.getCustNm()));
```

**Without `getter`/`setter` (infer from java_field):**
- `java_field: "custNm"` → `getCustNm()` / `setCustNm()`
- Apply standard JavaBean naming convention

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
    "overview": "Overview of the batch program's data flow (2-3 sentences)",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Customer Data Migration",
        "sql_query_id": "sel04",
        "direction": "DB_TO_PROCESS | PROCESS_TO_DB | BIDIRECTIONAL",
        "data_source": {
          "type": "DB | FILE | EXTERNAL",
          "description": "Where the data comes from"
        },
        "data_sink": {
          "type": "DB | FILE | EXTERNAL",
          "description": "Where the data goes to"
        },
        "path": "ItemReader.read() → Process → ItemWriter.write()",
        "sensitive_columns": ["cust_nm", "rrn_encr"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "XXXRegBAT.java",
      "target_method": "execute",
      "action": "ENCRYPT | DECRYPT | ENCRYPT_THEN_DECRYPT | SKIP",
      "reason": "Reason for this modification",
      "target_properties": ["custNm", "rrnEncr"],
      "insertion_point": "After reader.read() returns / Before writer.write() call",
      "code_pattern_hint": "vo.setCustNm(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, vo.getCustNm()));"
    }
  ]
}
```

### ★★★ SKIP Action Output Format (CRITICAL) ★★★

**When `action` is `"SKIP"`, you MUST set `target_method` and `file_name` to empty strings:**

```json
{
  "flow_id": "FLOW_001",
  "file_name": "",
  "target_method": "",
  "action": "SKIP",
  "reason": "Reason for skipping",
  "target_properties": [],
  "insertion_point": "",
  "code_pattern_hint": ""
}
```

### Batch-Specific Direction Values

| Direction | Description | Action |
|-----------|-------------|--------|
| `DB_TO_PROCESS` | ItemReader reads from DB | DECRYPT after read() |
| `PROCESS_TO_DB` | ItemWriter writes to DB | ENCRYPT before write() |
| `BIDIRECTIONAL` | Read from DB, process, write to DB | DECRYPT after read, ENCRYPT before write |

### Field Descriptions

| Field               | Description                                              | Example                                                       |
| ------------------- | -------------------------------------------------------- | ------------------------------------------------------------- |
| `flow_id`           | Reference to data_flow_analysis.flows[].flow_id          | `FLOW_001`, `FLOW_002`                                        |
| `sql_query_id`      | Matching sql_id from mapping_info                        | `sel04`, `upd01`                                              |
| `file_name`         | BAT.java file name to modify (**empty string for SKIP**) | `CmpgnCstmrRegBAT.java`                                       |
| `target_method`     | Method name to modify (**empty string for SKIP**)        | `execute`, `process`                                          |
| `action`            | Action to perform                                        | `ENCRYPT`, `DECRYPT`, `ENCRYPT_THEN_DECRYPT`, `SKIP`          |
| `target_properties` | Properties to encrypt/decrypt (array of java_field names)| `["custNm", "rrnEncr"]`                                       |
| `insertion_point`   | Insertion location description                           | `After reader.read() returns`, `Before writer.write() call`   |
| `code_pattern_hint` | Code pattern example                                     | `vo.setCustNm(SliEncryptionUtil.encrypt(...));`               |

### ⚠️ CRITICAL: Every Flow MUST Have a modification_instruction Entry ⚠️

**For EVERY flow in `data_flow_analysis.flows`, you MUST output a corresponding entry in `modification_instructions`.**

- If the flow requires encryption/decryption → output with `action: "ENCRYPT"` or `action: "DECRYPT"`
- If the flow does NOT require modification → output with `action: "SKIP"`, `file_name: ""`, `target_method: ""` and explain `reason`

---

## Example Output

### Example 1: Read-Process-Write with Encryption

**Scenario:**
- BAT.java reads customer data (SELECT), processes it, then updates (UPDATE)
- Both SELECT result and UPDATE input have sensitive columns

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Batch program reads customer data from source table, processes it, and updates target table. SELECT results need decryption, UPDATE inputs need encryption.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Customer Data Read",
        "sql_query_id": "sel04",
        "direction": "DB_TO_PROCESS",
        "data_source": {"type": "DB", "description": "SELECT from customer table"},
        "data_sink": {"type": "PROCESS", "description": "In-memory processing"},
        "path": "itemReader.read() → business logic",
        "sensitive_columns": ["cust_nm", "rrn_encr"]
      },
      {
        "flow_id": "FLOW_002",
        "flow_name": "Customer Data Update",
        "sql_query_id": "upd01",
        "direction": "PROCESS_TO_DB",
        "data_source": {"type": "PROCESS", "description": "Processed data"},
        "data_sink": {"type": "DB", "description": "UPDATE to customer table"},
        "path": "business logic → itemWriter.write()",
        "sensitive_columns": ["cust_nm", "rrn_encr"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "CmpgnCstmrRegBAT.java",
      "target_method": "execute",
      "action": "DECRYPT",
      "reason": "FLOW_001: SELECT results contain encrypted data, need decryption after read()",
      "target_properties": ["custNm", "rrnEncr"],
      "insertion_point": "Immediately after sel04.read() returns",
      "code_pattern_hint": "vo.setCustNm(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, vo.getCustNm()));\nvo.setRrnEncr(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.ENC_NO, vo.getRrnEncr()));"
    },
    {
      "flow_id": "FLOW_002",
      "file_name": "CmpgnCstmrRegBAT.java",
      "target_method": "execute",
      "action": "ENCRYPT",
      "reason": "FLOW_002: UPDATE input data needs encryption before write()",
      "target_properties": ["custNm", "rrnEncr"],
      "insertion_point": "Right before upd01.write() call",
      "code_pattern_hint": "updateVo.setCustNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, updateVo.getCustNm()));\nupdateVo.setRrnEncr(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.ENC_NO, updateVo.getRrnEncr()));"
    }
  ]
}
```

### Example 2: Read Only (No sensitive columns in SELECT)

**Scenario:**
- BAT.java reads status data (no sensitive columns)
- Phase 1 returned empty crypto_fields

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Batch program reads status data which doesn't contain sensitive columns. No encryption/decryption needed.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Status Data Read",
        "sql_query_id": "sel01",
        "direction": "DB_TO_PROCESS",
        "data_source": {"type": "DB", "description": "SELECT status data"},
        "data_sink": {"type": "PROCESS", "description": "Status processing"},
        "path": "itemReader.read() → status update",
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
      "reason": "FLOW_001: Phase 1 crypto_fields is empty - query does not involve encryption target columns",
      "target_properties": [],
      "insertion_point": "",
      "code_pattern_hint": ""
    }
  ]
}
```

### Example 3: Data Transfer with BIDIRECTIONAL flow

**Scenario:**
- BAT.java reads from source table, transfers to target table
- Same sensitive column in both source and target

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Batch program migrates customer data from source to target table. Source SELECT needs decryption, target INSERT needs encryption.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Customer Data Migration",
        "sql_query_id": "sel01",
        "direction": "BIDIRECTIONAL",
        "data_source": {"type": "DB", "description": "SELECT from source table"},
        "data_sink": {"type": "DB", "description": "INSERT to target table"},
        "path": "sourceReader.read() → process → targetWriter.write()",
        "sensitive_columns": ["emp_nm"]
      }
    ]
  },
  "modification_instructions": [
    {
      "flow_id": "FLOW_001",
      "file_name": "DataMigrationBAT.java",
      "target_method": "execute",
      "action": "DECRYPT",
      "reason": "FLOW_001 (DB_TO_PROCESS part): SELECT results contain encrypted emp_nm",
      "target_properties": ["empNm"],
      "insertion_point": "After sourceReader.read() returns",
      "code_pattern_hint": "srcVo.setEmpNm(SliEncryptionUtil.decrypt(0, SliEncryptionConstants.Policy.NAME, srcVo.getEmpNm()));"
    },
    {
      "flow_id": "FLOW_001",
      "file_name": "DataMigrationBAT.java",
      "target_method": "execute",
      "action": "ENCRYPT",
      "reason": "FLOW_001 (PROCESS_TO_DB part): INSERT input needs encryption for emp_nm",
      "target_properties": ["empNm"],
      "insertion_point": "Before targetWriter.write() call",
      "code_pattern_hint": "tgtVo.setEmpNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, tgtVo.getEmpNm()));"
    }
  ]
}
```

---

## Start Analysis Now

Based on the information above:

1. **Analyze the BAT.java source code** to find ItemReader/ItemWriter usage patterns
2. **Match each sql_id** with entries in `mapping_info.queries`
3. **Check `crypto_fields`** - if empty → `action: "SKIP"` with `file_name: ""` and `target_method: ""`
4. **Determine insertion points** based on read()/write() method calls
5. **Generate code_pattern_hint** using getter/setter from mapping_info

**★★★ CRITICAL REMINDER ★★★**
- **Trust Phase 1 results**: If `crypto_fields` is empty, the query does NOT need encryption/decryption
- **DO NOT invent fields**: Only use fields explicitly listed in `crypto_fields`
- **SKIP when appropriate**: Empty `crypto_fields` means `action: "SKIP"` with `file_name: ""` and `target_method: ""`
- **BAT.java is the only modification target**: All instructions should target the BAT file

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`. No other text allowed.**
