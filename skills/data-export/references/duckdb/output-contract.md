# DuckDB Export Output Contract

## Output files

### 1) Formal CSV

Path:

```text
jobs/{SESSION_ID}/data/<output_name>.csv
```

Rules:
- Must be the only CSV consumed by downstream profiling for this export step
- Filename must carry business meaning; never use `pivot.csv`
- Must be recorded in `duckdb_export_summary.json`

### 2) Summary JSON

Path:

```text
jobs/{SESSION_ID}/duckdb_export_summary.json
```

## Summary schema

```json
{
  "source_backend": "duckdb",
  "source_id": "duckdb.example.orders",
  "display_name": "DuckDB_航班经营结果视图",
  "db_path": "duckdb/demo.duckdb",
  "schema": "main",
  "object_name": "View_DWD_ZY_Flight_Results",
  "output_file": "jobs/<SESSION_ID>/data/duckdb_xxx.csv",
  "row_count": 1234,
  "selected_fields": ["航班日期", "航班号"],
  "filters": [
    {"field": "区域", "operator": "=", "value": "上海区域"}
  ],
  "date_ranges": [
    {"field": "航班日期", "start": "2025-01-01", "end": "2025-01-31"}
  ],
  "group_by": ["航班日期", "产品"],
  "aggregates": [
    {"field": "订单数", "function": "sum", "alias": "订单数合计"}
  ],
  "order_by": [
    {"field": "航班日期", "direction": "asc"}
  ],
  "limit": 50000,
  "sql": "SELECT ...",
  "exported_at": "2026-03-24T11:00:00+08:00"
}
```

## Validation rules

- `source_backend` must equal `duckdb`
- `source_id` must exist in SQLite registry
- `output_file` must exist
- `row_count` must equal actual CSV row count
- `sql` must be the exact SQL executed by the exporter
- every field in `selected_fields`, `filters`, `group_by`, `aggregates`, and `order_by` must be registered for that source
