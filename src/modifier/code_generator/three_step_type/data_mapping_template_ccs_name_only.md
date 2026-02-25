# Data Mapping Extraction (Phase 1) - CCS Version (Name Only)

## Role

You are an expert in analyzing DQM.xml resultMap mappings and SQL queries.
Your task is to extract **query-based data mapping information** from SQL queries.

**Important**:
- This is an **extraction and analysis** task only - you are NOT modifying any code
- Field mappings from `resultMap` tags are provided with each query - use them to determine Java field names
- You are providing structured information for the next phase (Planning)
- **This template focuses ONLY on NAME fields** - ignore other sensitive data types (DOB, RRN, etc.)

---

## ★★★ Target Table Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table and NAME columns specified below.**

{{ table_info }}

**table_info.columns Structure:**
- `name`: Column name (always present) - **this is the DB column to find in SQL**
- `new_column`: Whether this is a new column (boolean)
- `column_type`: Type of sensitive data - **ONLY `"name"` is processed**
- `encryption_code`: Direct policy constant (optional)

**CRITICAL: Only process columns with `column_type: "name"` or name-related encryption_code.**
Columns with other types (dob, rrn, etc.) should be IGNORED.

---

## SQL Queries with Field Mappings

{{ sql_queries_with_mappings }}

---

## Output Format (★★★ JSON ONLY ★★★)

**CRITICAL OUTPUT RULES:**
1. Output **ONLY** valid JSON - no explanations, no markdown, no comments
2. Do **NOT** include ```json or ``` markers
3. Do **NOT** add trailing commas
4. Use **double quotes** for all strings and keys
5. Start directly with `{` and end with `}`

**JSON Structure:**

```json
{
  "queries": [
    {
      "query_id": "com.example.mapper.UserMapper.selectUser",
      "command_type": "SELECT",
      "sql_summary": "Brief description of what the query does",
      "input_mapping": {
        "type_category": "PRIMITIVE | MAP | VO | NONE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "PRIMITIVE | MAP | VO | NONE",
        "class_name": "UserVO",
        "crypto_fields": [
          {
            "column_name": "USER_NM",
            "java_field": "userNm"
          }
        ]
      }
    }
  ]
}
```

---

## Field Descriptions

| Field           | Description                                                                |
| --------------- | -------------------------------------------------------------------------- |
| `query_id`      | Unique ID of the query                                                     |
| `command_type`  | SQL command type: `SELECT`, `INSERT`, `UPDATE`, `DELETE`                   |
| `sql_summary`   | Brief description of what the query does                                   |
| `type_category` | Type of Java object: `VO`, `MAP`, `PRIMITIVE`, `NONE`                      |
| `class_name`    | Simple class name without package (e.g., `UserVO`, `HashMap`)              |
| `column_name`   | **Original DB column name** (the target column from table_info)            |
| `java_field`    | For VO: resultMap `property` value. For Map: SQL alias if used, else column name (camelCase) |

---

## Extraction Guidelines

### 1. Identify Input/Output Types

- **Look for `Parameter Type` and `Result Type`** listed under each query
- **class_name**: Always use simple class name (e.g., `UserVO` not `com.example.UserVO`)

### 2. Handle Map Types

**For Input (parameterType is Map):**
- `#{keyName}` in SQL → `java_field` is `keyName`

**For Output (resultType is Map):**
- With alias: `SELECT col AS alias` → `java_field` is `alias`
- Without alias: `java_field` is `column_name`

### 3. Handle VO Types with resultMap

**Each query may include "Relevant Field Mappings for Target Columns" section.**

When provided:
- Use the exact `java_field` from `Column X → Java field Y` mapping
- **Do NOT include `getter` and `setter`**

When NOT provided:
- Infer `java_field` by converting column name to camelCase
- `UPPER_SNAKE` → `camelCase`: `EMP_NM` → `empNm`

### ★★★ 4. Handle SQL Aliases (CRITICAL) ★★★

**SQL aliases affect how columns map to Java fields. You MUST trace the full chain:**

```
Original DB Column → SQL Alias → resultMap column → resultMap property (java_field)
```

**Example Scenario:**
```sql
SELECT USER_NM AS TRTR_NM FROM TB_USER
```
```xml
<resultMap>
  <result property="trtrNm" column="TRTR_NM"/>
</resultMap>
```

**Analysis:**
1. Target column: `USER_NM` (from table_info)
2. SQL uses alias: `USER_NM AS TRTR_NM`
3. resultMap column: `TRTR_NM` (matches the alias, NOT the original column)
4. resultMap property: `trtrNm` (this is the java_field)

**Correct Output:**
```json
{
  "column_name": "USER_NM",
  "java_field": "trtrNm"
}
```

**Common Alias Patterns:**
- `SELECT COLUMN_A AS ALIAS_B` → Find resultMap entry where `column="ALIAS_B"` → Use its `property` as java_field
- Multiple aliases for same column: `SELECT USER_NM AS TRTR_NM, USER_NM AS ACPNR_NM` → Creates separate entries
- Column without alias: `SELECT USER_NM` → Find resultMap where `column="USER_NM"` directly

**IMPORTANT:**
- `column_name` is always the **original DB column** (the target column from table_info)
- `java_field` comes from **resultMap property** (trace through alias if used)
- When a target column appears multiple times with different aliases, create separate crypto_field entries for each

### 5. Handle SELECT * Queries

When SQL uses `SELECT *`:
1. **Include ONLY NAME columns** from table_info in `output_mapping.crypto_fields`
2. Do NOT include non-name sensitive columns (dob, rrn, etc.)
3. For each name column, find its mapping in resultMap
4. If no specific resultMap entry, infer java_field using camelCase conversion

---

## Examples

### Example 1: SELECT with SQL Alias (★ Most Common Pattern ★)

**Input:**
```
### Query 1: selectUser (SELECT)
**SQL:**
SELECT USER_NM AS TRTR_NM, USER_NM AS ACPNR_NM FROM TB_USER WHERE USER_ID = #{userId}

- **Parameter Type:** `String`
- **Result Type:** `com.example.vo.UserVO`

**Relevant Field Mappings for Target Columns (USER_NM):**
- Column `TRTR_NM` → Java field `trtrNm`
- Column `ACPNR_NM` → Java field `acpnrNm`
```

**Analysis:**
- Target column: `USER_NM` (name type)
- `USER_NM AS TRTR_NM` → resultMap `column="TRTR_NM"` → `property="trtrNm"`
- `USER_NM AS ACPNR_NM` → resultMap `column="ACPNR_NM"` → `property="acpnrNm"`

**Output:**
```json
{
  "queries": [
    {
      "query_id": "selectUser",
      "command_type": "SELECT",
      "sql_summary": "SELECT USER_NM with aliases TRTR_NM, ACPNR_NM",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "UserVO",
        "crypto_fields": [
          { "column_name": "USER_NM", "java_field": "trtrNm" },
          { "column_name": "USER_NM", "java_field": "acpnrNm" }
        ]
      }
    }
  ]
}
```

### Example 2: SELECT without Alias

**Input:**
```
### Query 2: selectEmp (SELECT)
**SQL:**
SELECT EMP_NM FROM TB_EMP WHERE EMP_ID = #{empId}

- **Parameter Type:** `String`
- **Result Type:** `com.example.vo.EmpVO`

**Relevant Field Mappings for Target Columns (EMP_NM):**
- Column `EMP_NM` → Java field `empNm`
```

**Output:**
```json
{
  "queries": [
    {
      "query_id": "selectEmp",
      "command_type": "SELECT",
      "sql_summary": "SELECT EMP_NM from TB_EMP",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "EmpVO",
        "crypto_fields": [
          { "column_name": "EMP_NM", "java_field": "empNm" }
        ]
      }
    }
  ]
}
```

### Example 3: UPDATE with name column

**Input:**
```
### Query 3: updateUser (UPDATE)
**SQL:**
UPDATE TB_USER SET USER_NM = #{userNm} WHERE USER_NM = #{searchName}

- **Parameter Type:** `java.util.HashMap`
```

**Output:**
```json
{
  "queries": [
    {
      "query_id": "updateUser",
      "command_type": "UPDATE",
      "sql_summary": "UPDATE USER_NM WHERE USER_NM",
      "input_mapping": {
        "type_category": "MAP",
        "class_name": "HashMap",
        "crypto_fields": [
          { "column_name": "USER_NM", "java_field": "userNm" },
          { "column_name": "USER_NM", "java_field": "searchName" }
        ]
      },
      "output_mapping": {
        "type_category": "NONE",
        "class_name": null,
        "crypto_fields": []
      }
    }
  ]
}
```

### Example 4: SELECT * with VO result

**Input:**
- Query: `SELECT * FROM TB_USER WHERE USER_ID = #{userId}`
- Result Type: `com.example.vo.UserVO`
- Target name column: `USER_NM`

**Analysis:**
- `SELECT *` returns ALL columns including name columns
- Only include name columns in crypto_fields

**Output:**
```json
{
  "queries": [
    {
      "query_id": "selectAll",
      "command_type": "SELECT",
      "sql_summary": "SELECT * - returns ALL columns including USER_NM",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "UserVO",
        "crypto_fields": [
          { "column_name": "USER_NM", "java_field": "userNm" }
        ]
      }
    }
  ]
}
```

### Example 5: MERGE/INSERT with data from target table (DB → DB transfer)

**Input:**
```
### Query 5: mergeToOtherTable (MERGE)
**SQL:**
MERGE INTO non_target_table tgt
USING (SELECT user_id, user_nm FROM target_table WHERE status = 'A') src
ON (tgt.user_id = src.user_id)
WHEN MATCHED THEN UPDATE SET tgt.user_nm = src.user_nm
WHEN NOT MATCHED THEN INSERT (user_id, user_nm) VALUES (src.user_id, src.user_nm)

- **Parameter Type:** `None`
- **Result Type:** `int`
```

**Analysis:**
- This query moves data **from target_table to non_target_table** within SQL
- The name column (`USER_NM`) is **already encrypted in target_table**
- Data flows directly DB → DB without passing through Java layer
- **No encryption/decryption needed** - encrypted values are transferred as-is

**Output:**
```json
{
  "queries": [
    {
      "query_id": "mergeToOtherTable",
      "command_type": "MERGE",
      "sql_summary": "MERGE data from target_table to non_target_table - DB to DB transfer, already encrypted",
      "input_mapping": {
        "type_category": "NONE",
        "class_name": null,
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "NONE",
        "class_name": null,
        "crypto_fields": []
      }
    }
  ]
}
```

**★ Key Point:** When sensitive data moves **directly between tables in SQL** (MERGE INTO, INSERT INTO ... SELECT), the data is already encrypted in the source table. No Java-layer encryption/decryption is required - `crypto_fields` should be empty.

---

## Start Extraction Now

Analyze the provided SQL queries and extract field mappings.

**Key Points:**
1. `column_name` = **Original DB column** from table_info
2. `java_field` = **resultMap property** (trace through SQL alias if present)
3. When target column uses alias, find resultMap entry matching the **alias**, not the original column
4. Do NOT include getter/setter
5. **ONLY process NAME type columns** - ignore DOB, RRN, and other sensitive data types

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`.**
