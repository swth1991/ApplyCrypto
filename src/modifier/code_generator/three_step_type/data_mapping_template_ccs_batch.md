# Data Mapping Extraction (Phase 1) - CCS Batch Version

## Role

You are an expert in analyzing Java Batch programs, VO classes, and SQL queries.
Your task is to analyze the **BAT.java code's data flow** to extract field mappings between SQL queries and Java VO objects.

**Important**:

- This is an **extraction and analysis** task only
- You are NOT modifying any code
- Analyze `itemFactory.getItemReader()` / `getItemWriter()` patterns to map SQL IDs to VO classes
- Analyze `vo.getXxx()` / `vo.setXxx()` patterns to identify actual field usage
- You are providing structured information to help the next phase (Planning) understand how data flows between Java and DB

---

## ★★★ Target Table Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table and columns specified below.**

{{ table_info }}

**table_info.columns Structure:**

Each column in `table_info.columns` may contain:
- `name`: Column name (always present) - **this is the DB column name to match in SQL**
- `new_column`: Whether this is a new column (boolean)
- `column_type`: Type of sensitive data - `"name"`, `"dob"`, or `"rrn"` (optional)
- `encryption_code`: Direct policy constant - e.g., `"SliEncryptionConstants.Policy.NAME"` (optional)

**CRITICAL: Every column listed in table_info.columns IS an encryption target.**
Do NOT skip any column. Even if the column name seems unusual (e.g., `gvnm`, `aenam`), it must be included in `crypto_fields`.

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
String rrnEncr = rea01Vo.getRrnEncr();

// Writing to another VO
insVo.setRrnEncr(rrnEncr);
```

This tells us:
- `rrnEncr` field is being read and written
- The field flows from `rea01Vo` to `insVo`

### 3. Map Columns to Java Fields

For each target column in `table_info.columns`:
1. Find the corresponding Java field in BATVO files
2. Identify getter/setter methods from the VO class definitions
3. If VO file not provided, infer using camelCase conversion:
   - `RRN_ENCR` → `rrnEncr`
   - `CUST_NM` → `custNm`

### 4. Handle Different Query Types

**SELECT queries (ItemReader):**
- Output mapping: VO receives data from DB
- Need to identify: which fields receive encrypted data from DB

**INSERT/UPDATE queries (ItemWriter):**
- Input mapping: VO sends data to DB
- Need to identify: which fields need encryption before DB write

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
            "column_name": "RRN_ENCR",
            "java_field": "rrnEncr",
            "getter": "getRrnEncr",
            "setter": "setRrnEncr"
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
| `sql_summary`   | Brief description of what the query does with target columns                         |
| `type_category` | Type of Java object: `VO`, `MAP`, `PRIMITIVE`, `NONE`                                |
| `class_name`    | Simple class name without package path (e.g., `XXXBatVO`, `HashMap`)                 |
| `column_name`   | Original DB column name (from table_info.columns)                                    |
| `java_field`    | Java field name in the VO class                                                      |
| `getter`        | Getter method name (from VO class or inferred: `getFieldName`)                       |
| `setter`        | Setter method name (from VO class or inferred: `setFieldName`)                       |

---

## Complete Examples

### Example 1: SELECT query with VO result

**BAT.java pattern:**
```java
ItemReader<CmpgnCstmrBatVO> sel04 = itemFactory.getItemReader("sel04", CmpgnCstmrBatVO.class);

while (sel04.next()) {
    CmpgnCstmrBatVO vo = sel04.read();
    String rrnEncr = vo.getRrnEncr();
    // process data...
}
```

**BATVO file shows:**
```java
public class CmpgnCstmrBatVO {
    private String rrnEncr;
    public String getRrnEncr() { return rrnEncr; }
    public void setRrnEncr(String rrnEncr) { this.rrnEncr = rrnEncr; }
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
      "description": "Select customer data including RRN"
    }
  ],
  "queries": [
    {
      "query_id": "sel04",
      "command_type": "SELECT",
      "sql_summary": "SELECT customer data with RRN_ENCR column",
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
            "column_name": "RRN_ENCR",
            "java_field": "rrnEncr",
            "getter": "getRrnEncr",
            "setter": "setRrnEncr"
          }
        ]
      }
    }
  ]
}
```

### Example 2: INSERT/UPDATE query with VO input

**BAT.java pattern:**
```java
ItemWriter upd01 = itemFactory.getItemWriter("upd01");

CmpgnCstmrBatVO updateVo = new CmpgnCstmrBatVO();
updateVo.setRrnEncr(encryptedRrn);
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
      "description": "Update customer RRN"
    }
  ],
  "queries": [
    {
      "query_id": "upd01",
      "command_type": "UPDATE",
      "sql_summary": "UPDATE customer data with RRN_ENCR column",
      "input_mapping": {
        "type_category": "VO",
        "class_name": "CmpgnCstmrBatVO",
        "crypto_fields": [
          {
            "column_name": "RRN_ENCR",
            "java_field": "rrnEncr",
            "getter": "getRrnEncr",
            "setter": "setRrnEncr"
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

### Example 3: Data flow between multiple VOs

**BAT.java pattern:**
```java
// Read from source VO
ItemReader<SourceBatVO> sel01 = itemFactory.getItemReader("sel01", SourceBatVO.class);
ItemWriter ins01 = itemFactory.getItemWriter("ins01");

while (sel01.next()) {
    SourceBatVO srcVo = sel01.read();
    TargetBatVO tgtVo = new TargetBatVO();

    // Data flow: source -> target
    String custNm = srcVo.getCustNm();
    tgtVo.setCustNm(custNm);

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
      "sql_summary": "SELECT source data with CUST_NM column",
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
            "column_name": "CUST_NM",
            "java_field": "custNm",
            "getter": "getCustNm",
            "setter": "setCustNm"
          }
        ]
      }
    },
    {
      "query_id": "ins01",
      "command_type": "INSERT",
      "sql_summary": "INSERT target data with CUST_NM column",
      "input_mapping": {
        "type_category": "VO",
        "class_name": "TargetBatVO",
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

---

## Start Extraction Now

Analyze the BAT.java source code, BATVO files, and SQL queries:

1. **First**: Find all `itemFactory.getItemReader()` / `getItemWriter()` calls to map SQL IDs to VO classes
2. **Second**: For each target column in `table_info.columns`, find the corresponding Java field in BATVO
3. **Third**: Determine which queries involve the target columns (SELECT → output_mapping, INSERT/UPDATE → input_mapping)
4. **Fourth**: Include getter/setter from BATVO if available, otherwise infer from field name

**REMINDER: Output ONLY the JSON object. Start directly with `{` and end with `}`.**
