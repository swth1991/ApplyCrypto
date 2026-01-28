# Data Mapping Extraction (Phase 1) - CCS Version (Name Only)

## Role

You are an expert in analyzing DQM.xml resultMap mappings, Java VO classes, and SQL queries.
Your task is to extract **query-based data mapping information** from the provided SQL queries.

**Important**:

- This is an **extraction and analysis** task only
- You are NOT modifying any code
- Field mappings from `resultMap` tags are already provided with each query - use them directly
- You are providing structured information to help the next phase (Planning) understand how data flows between Java and DB
- **This template focuses ONLY on NAME fields** - ignore other sensitive data types (DOB, RRN, etc.)

---

## ★★★ Target Table Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table and NAME columns specified below.**

{{ table_info }}

**table_info.columns Structure:**

Each column in `table_info.columns` may contain:
- `name`: Column name (always present) - **this is the DB column name to match in SQL**
- `new_column`: Whether this is a new column (boolean)
- `column_type`: Type of sensitive data - **ONLY `"name"` is processed** (other types are ignored)
- `encryption_code`: Direct policy constant - e.g., `"SliEncryptionConstants.Policy.NAME"` (optional)

**CRITICAL: Only process columns with `column_type: "name"` or name-related encryption_code.**
Columns with other types (dob, rrn, etc.) should be IGNORED in this template.

---

## SQL Queries with Relevant Field Mappings

Below are the SQL queries to analyze. Each query includes **only the relevant field mappings** for the target columns listed above. Use these mappings to determine the exact Java field names.

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
        "class_name": "HashMap",
        "crypto_fields": [
          {
            "column_name": "emp_nm",
            "java_field": "empNm"
          }
        ]
      }
    }
  ]
}
```

---

## Field Descriptions

| Field           | Description                                                                          |
| --------------- | ------------------------------------------------------------------------------------ |
| `query_id`      | Unique ID of the query (e.g., `com.example.mapper.UserMapper.selectUser`)            |
| `command_type`  | SQL command type: `SELECT`, `INSERT`, `UPDATE`, `DELETE`                             |
| `sql_summary`   | Brief description of what the query does with target columns                         |
| `type_category` | Type of Java object: `VO`, `MAP`, `PRIMITIVE`, `NONE`                                |
| `class_name`    | Simple class name without package path (e.g., `UserVO`, `HashMap`, `String`)         |
| `column_name`   | Original DB column name                                                              |
| `java_field`    | For VO: field name, For Map: key name (alias if used in SQL, otherwise column name) |
| `getter`        | Getter method name (**ONLY when VO file is provided in context**)                    |
| `setter`        | Setter method name (**ONLY when VO file is provided in context**)                    |

---

## Extraction Guidelines

### 1. Identify Input/Output Types

- **Look for `Parameter Type` and `Result Type`** listed under each query
- **class_name**: Always use simple class name (e.g., `UserVO` not `com.example.UserVO`, `HashMap` not `java.util.HashMap`)

### 2. Handle Map Types

**For Input (parameterType is Map):**
- `#{keyName}` in SQL → `java_field` is `keyName`

**For Output (resultType is Map):**
- With alias: `SELECT col AS alias` → `java_field` is `alias`
- Without alias: `java_field` is `column_name`

**Example:**
```sql
SELECT emp_nm FROM TB_EMP WHERE emp_nm = #{searchName}
```
- Input: `java_field: "searchName"` (from `#{searchName}`)
- Output: `emp_nm` → `java_field: "emp_nm"` (no alias)

### 3. Handle VO Types (★ Use inline field mappings ★)

**Each query includes "Relevant Field Mappings for Target Columns" section directly.**

**When inline field mappings are provided:**
- Look for the "Relevant Field Mappings for Target Columns" section under each query
- Use the exact `java_field` from `Column X → Java field Y` mapping
- **Do NOT include `getter` and `setter`** (resultMap provides the mapping directly)

**Example:** If a query shows:
```
**Relevant Field Mappings for Target Columns (EMP_NM):**
- Column `EMP_NM` → Java field `empNm`
```

Then output:
```json
{
  "column_name": "EMP_NM",
  "java_field": "empNm"
}
```

**When inline field mappings are NOT available (fallback):**
- Infer `java_field` by converting column name to camelCase
- `snake_case` → `camelCase`: `emp_nm` → `empNm`
- `UPPER_SNAKE` → `camelCase`: `EMP_NM` → `empNm`, `CUST_NM` → `custNm`

### 4. Handle SELECT * Queries (★★★ CRITICAL ★★★)

When SQL uses `SELECT *` or `SELECT t.*`:

1. **Include ONLY NAME columns** from `{{ table_info }}` in `output_mapping.crypto_fields`
2. Do NOT include non-name sensitive columns (dob, rrn, etc.)
3. `SELECT *` returns ALL columns - but we only process name fields

**For java_field:**
- Map result type: use column name as-is
- VO result type with inline mappings: use the `java_field` from "Relevant Field Mappings" section
- VO result type without mappings: infer using camelCase conversion

---

## Complete Examples

### Example 1: SELECT with VO result (inline mapping provided)

**Input (query with inline mappings):**
```
### Query 1: selectEmp (SELECT)
**SQL:**
SELECT emp_nm FROM TB_EMP WHERE emp_id = #{empId}

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
      "query_id": "com.example.mapper.EmpMapper.selectEmp",
      "command_type": "SELECT",
      "sql_summary": "SELECT emp_nm from TB_EMP",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "EmpVO",
        "crypto_fields": [
          { "column_name": "emp_nm", "java_field": "empNm" }
        ]
      }
    }
  ]
}
```

**★ Note:** No `getter`/`setter` fields - the exact `java_field` is taken from resultMap mapping.

---

### Example 2: SELECT with Map result (aliases)

**Input:**
- Query: `SELECT emp_nm AS name FROM TB_EMP WHERE emp_nm = #{searchName}`
- Parameter Type: `java.util.HashMap`
- Result Type: `java.util.HashMap`

**Output:**
```json
{
  "queries": [
    {
      "query_id": "com.example.mapper.EmpMapper.searchByName",
      "command_type": "SELECT",
      "sql_summary": "SELECT by emp_nm - emp_nm in WHERE and result",
      "input_mapping": {
        "type_category": "MAP",
        "class_name": "HashMap",
        "crypto_fields": [
          { "column_name": "emp_nm", "java_field": "searchName" }
        ]
      },
      "output_mapping": {
        "type_category": "MAP",
        "class_name": "HashMap",
        "crypto_fields": [
          { "column_name": "emp_nm", "java_field": "name" }
        ]
      }
    }
  ]
}
```

---

### Example 3: UPDATE with name column in SET and WHERE

**Input:**
- Query: `UPDATE TB_EMP SET emp_nm = #{newName} WHERE emp_nm = #{searchName}`
- Parameter Type: `java.util.HashMap`

**Output:**
```json
{
  "queries": [
    {
      "query_id": "com.example.mapper.EmpMapper.updateName",
      "command_type": "UPDATE",
      "sql_summary": "UPDATE emp_nm WHERE emp_nm - both are name fields",
      "input_mapping": {
        "type_category": "MAP",
        "class_name": "HashMap",
        "crypto_fields": [
          { "column_name": "emp_nm", "java_field": "searchName" },
          { "column_name": "emp_nm", "java_field": "newName" }
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

---

### Example 4: SELECT * with Map result

**Input:**
- Query: `SELECT * FROM TB_EMP WHERE emp_id = #{empId}`
- Result Type: `java.util.HashMap`
- Target table has name column: `emp_nm`

**Analysis:**
- `SELECT *` returns ALL columns including name field
- Only include name columns in crypto_fields
- No alias used → java_field = column_name

**Output:**
```json
{
  "queries": [
    {
      "query_id": "com.example.mapper.EmpMapper.selectAll",
      "command_type": "SELECT",
      "sql_summary": "SELECT * - returns ALL columns including emp_nm",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "MAP",
        "class_name": "HashMap",
        "crypto_fields": [
          { "column_name": "emp_nm", "java_field": "emp_nm" }
        ]
      }
    }
  ]
}
```

---

### Example 5: SELECT * with VO result (★ VO file NOT provided ★)

**Input:**
- Query: `SELECT * FROM TARGET_TABLE WHERE USER_UUID = #{userUuid}`
- Result Type: `com.example.vo.UserInfoVO` (★ VO file NOT in context ★)
- Target table has name column: `USER_NM`

**Analysis:**
- `SELECT *` returns ALL columns
- VO file is NOT provided → infer java_field using camelCase
- **No getter/setter** because VO structure is unknown
- Only include name columns

**Output:**
```json
{
  "queries": [
    {
      "query_id": "com.example.mapper.UserMapper.selectByUuid",
      "command_type": "SELECT",
      "sql_summary": "SELECT * - returns ALL columns including USER_NM",
      "input_mapping": {
        "type_category": "PRIMITIVE",
        "class_name": "String",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "UserInfoVO",
        "crypto_fields": [
          { "column_name": "USER_NM", "java_field": "userNm" }
        ]
      }
    }
  ]
}
```

**★ Key Point:** No `getter`/`setter` fields because VO file was not provided. Only `column_name` and inferred `java_field` are included.

---

## Start Extraction Now

Analyze the provided SQL queries using the inline field mappings shown with each query.

**Key Points:**
- Each query has a "Relevant Field Mappings for Target Columns" section - use it directly
- For SELECT queries: mappings show `Column X → Java field Y` format
- For INSERT/UPDATE queries: use `#{fieldName}` patterns from SQL
- Do NOT include getter/setter - resultMap provides the mapping directly
- **ONLY process NAME type columns** - ignore DOB, RRN, and other sensitive data types

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`.**
