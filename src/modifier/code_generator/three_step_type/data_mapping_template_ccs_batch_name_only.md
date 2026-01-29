# Data Mapping Extraction (Phase 1) - CCS Batch Version (Name Only)

## Role

You are an expert in analyzing Java Batch programs, VO classes, and SQL queries.
Your task is to analyze the **BAT.java code's data flow** to extract field mappings between SQL queries and Java VO objects.

**Important**:

- This is an **extraction and analysis** task only
- You are NOT modifying any code
- Analyze `itemFactory.getItemReader()` / `getItemWriter()` patterns to map SQL IDs to VO classes
- Analyze `vo.getXxx()` / `vo.setXxx()` patterns to identify actual field usage
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

## BAT.java Source Code (Main Analysis Target)

Analyze this batch program to understand the data flow:

{{ bat_source }}

---

## BATVO Files (VO Class Definitions)

These are the VO classes used by the batch program:

{{ batvo_files }}

---

## SQL Queries (from XXX_SQL.xml)

{{ sql_queries }}

{% if xml_content %}
## Raw XML Content (Reference)

{{ xml_content }}
{% endif %}

---

## Analysis Guidelines

### 1. Extract SQL ID to VO Class Mappings

Look for patterns like:
```java
ItemReader<XXXBatVO> sel04 = itemFactory.getItemReader("sel04", XXXBatVO.class);
ItemWriter upd01 = itemFactory.getItemWriter("upd01");
```

From this pattern, extract:
- `sql_id`: "sel04"
- `vo_class`: "XXXBatVO"
- `operation`: "SELECT" (for ItemReader) or "INSERT/UPDATE" (for ItemWriter)

### 2. Analyze Data Flow Patterns

Look for how data moves between VOs:
```java
// Reading from one VO
String custNm = rea01Vo.getCustNm();

// Writing to another VO
insVo.setCustNm(custNm);
```

This tells us:
- `custNm` field (NAME type) is being read and written
- The field flows from `rea01Vo` to `insVo`

### 3. Map Columns to Java Fields (NAME Type Only)

For each target column in `table_info.columns` where `column_type: "name"`:
1. Find the corresponding Java field in BATVO files
2. Identify getter/setter methods from the VO class definitions
3. If VO file not provided, infer using camelCase conversion:
   - `CUST_NM` → `custNm`
   - `EMP_NM` → `empNm`

### 4. Handle Different Query Types

**SELECT queries (ItemReader):**
- Output mapping: VO receives data from DB
- Need to identify: which NAME fields receive encrypted data from DB

**INSERT/UPDATE queries (ItemWriter):**
- Input mapping: VO sends data to DB
- Need to identify: which NAME fields need encryption before DB write

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
  "sql_vo_mappings": [
    {
      "sql_id": "sel04",
      "vo_class": "XXXBatVO",
      "operation": "SELECT",
      "description": "Brief description of what this query does"
    }
  ],
  "queries": [
    {
      "query_id": "sel04",
      "command_type": "SELECT",
      "sql_summary": "Brief description of what the query does",
      "input_mapping": {
        "type_category": "VO | MAP | PRIMITIVE | NONE",
        "class_name": "XXXBatVO",
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO | MAP | PRIMITIVE | NONE",
        "class_name": "XXXBatVO",
        "crypto_fields": [
          {
            "column_name": "CUST_NM",
            "java_field": "custNm",
            "getter": "getCustNm",
            "setter": "setCustNm"
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
| `sql_id`        | SQL query ID from XML (e.g., `sel04`, `upd01`)                                       |
| `vo_class`      | VO class name used with this query (simple name, e.g., `XXXBatVO`)                   |
| `operation`     | Query type: `SELECT`, `INSERT`, `UPDATE`, `DELETE`                                   |
| `query_id`      | Same as sql_id                                                                       |
| `command_type`  | SQL command type: `SELECT`, `INSERT`, `UPDATE`, `DELETE`                             |
| `sql_summary`   | Brief description of what the query does with NAME columns                           |
| `type_category` | Type of Java object: `VO`, `MAP`, `PRIMITIVE`, `NONE`                                |
| `class_name`    | Simple class name without package path (e.g., `XXXBatVO`, `HashMap`)                 |
| `column_name`   | Original DB column name (NAME type columns only)                                     |
| `java_field`    | Java field name in the VO class                                                      |
| `getter`        | Getter method name (from VO class or inferred: `getFieldName`)                       |
| `setter`        | Setter method name (from VO class or inferred: `setFieldName`)                       |

---

## Complete Examples

### Example 1: SELECT query with VO result (NAME field only)

**BAT.java pattern:**
```java
ItemReader<CmpgnCstmrBatVO> sel04 = itemFactory.getItemReader("sel04", CmpgnCstmrBatVO.class);

while (sel04.next()) {
    CmpgnCstmrBatVO vo = sel04.read();
    String custNm = vo.getCustNm();
    // process data...
}
```

**BATVO file shows:**
```java
public class CmpgnCstmrBatVO {
    private String custNm;
    public String getCustNm() { return custNm; }
    public void setCustNm(String custNm) { this.custNm = custNm; }
}
```

**Output:**
```json
{
  "sql_vo_mappings": [
    {
      "sql_id": "sel04",
      "vo_class": "CmpgnCstmrBatVO",
      "operation": "SELECT",
      "description": "Select customer data including name"
    }
  ],
  "queries": [
    {
      "query_id": "sel04",
      "command_type": "SELECT",
      "sql_summary": "SELECT customer data with CUST_NM column",
      "input_mapping": {
        "type_category": "NONE",
        "class_name": null,
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "CmpgnCstmrBatVO",
        "crypto_fields": [
          {
            "column_name": "CUST_NM",
            "java_field": "custNm",
            "getter": "getCustNm",
            "setter": "setCustNm"
          }
        ]
      }
    }
  ]
}
```

### Example 2: INSERT/UPDATE query with VO input (NAME field only)

**BAT.java pattern:**
```java
ItemWriter upd01 = itemFactory.getItemWriter("upd01");

CmpgnCstmrBatVO updateVo = new CmpgnCstmrBatVO();
updateVo.setCustNm(encryptedName);
upd01.write(updateVo);
```

**Output:**
```json
{
  "sql_vo_mappings": [
    {
      "sql_id": "upd01",
      "vo_class": "CmpgnCstmrBatVO",
      "operation": "UPDATE",
      "description": "Update customer name"
    }
  ],
  "queries": [
    {
      "query_id": "upd01",
      "command_type": "UPDATE",
      "sql_summary": "UPDATE customer data with CUST_NM column",
      "input_mapping": {
        "type_category": "VO",
        "class_name": "CmpgnCstmrBatVO",
        "crypto_fields": [
          {
            "column_name": "CUST_NM",
            "java_field": "custNm",
            "getter": "getCustNm",
            "setter": "setCustNm"
          }
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

### Example 3: Data flow between multiple VOs (NAME fields only)

**BAT.java pattern:**
```java
// Read from source VO
ItemReader<SourceBatVO> sel01 = itemFactory.getItemReader("sel01", SourceBatVO.class);
ItemWriter ins01 = itemFactory.getItemWriter("ins01");

while (sel01.next()) {
    SourceBatVO srcVo = sel01.read();
    TargetBatVO tgtVo = new TargetBatVO();

    // Data flow: source -> target (NAME field)
    String empNm = srcVo.getEmpNm();
    tgtVo.setEmpNm(empNm);

    ins01.write(tgtVo);
}
```

**Output:**
```json
{
  "sql_vo_mappings": [
    {
      "sql_id": "sel01",
      "vo_class": "SourceBatVO",
      "operation": "SELECT",
      "description": "Select source data"
    },
    {
      "sql_id": "ins01",
      "vo_class": "TargetBatVO",
      "operation": "INSERT",
      "description": "Insert target data"
    }
  ],
  "queries": [
    {
      "query_id": "sel01",
      "command_type": "SELECT",
      "sql_summary": "SELECT source data with EMP_NM column",
      "input_mapping": {
        "type_category": "NONE",
        "class_name": null,
        "crypto_fields": []
      },
      "output_mapping": {
        "type_category": "VO",
        "class_name": "SourceBatVO",
        "crypto_fields": [
          {
            "column_name": "EMP_NM",
            "java_field": "empNm",
            "getter": "getEmpNm",
            "setter": "setEmpNm"
          }
        ]
      }
    },
    {
      "query_id": "ins01",
      "command_type": "INSERT",
      "sql_summary": "INSERT target data with EMP_NM column",
      "input_mapping": {
        "type_category": "VO",
        "class_name": "TargetBatVO",
        "crypto_fields": [
          {
            "column_name": "EMP_NM",
            "java_field": "empNm",
            "getter": "getEmpNm",
            "setter": "setEmpNm"
          }
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

## Start Extraction Now

Analyze the BAT.java source code, BATVO files, and SQL queries:

1. **First**: Find all `itemFactory.getItemReader()` / `getItemWriter()` calls to map SQL IDs to VO classes
2. **Second**: For each NAME-type target column in `table_info.columns`, find the corresponding Java field in BATVO
3. **Third**: Determine which queries involve the NAME columns (SELECT → output_mapping, INSERT/UPDATE → input_mapping)
4. **Fourth**: Include getter/setter from BATVO if available, otherwise infer from field name
5. **IMPORTANT**: Only process columns with `column_type: "name"` - ignore DOB, RRN, and other types

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`.**
