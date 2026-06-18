# data-export

`RA:data-export` 是 RealAnalyst 的统一正式取数 skill。Tableau、DuckDB、MySQL 和 ClickHouse 都从这里进入。

它解决的问题是：让 Codex 在写报告前，只从已注册、可审计、可复核的数据源导出 CSV，而不是自由 SQL 或临时下载。

## 后端入口

| 后端 | 推荐脚本 | 直接脚本 |
| --- | --- | --- |
| Tableau | `scripts/tableau/tableau_export_with_meta.py` | `scripts/tableau/export_source.py` |
| DuckDB | `scripts/duckdb/duckdb_export_with_meta.py` | `scripts/duckdb/export_duckdb_source.py` |
| MySQL | `scripts/mysql/mysql_export_with_meta.py` | `scripts/mysql/export_mysql_source.py` |
| ClickHouse | `scripts/clickhouse/clickhouse_export_with_meta.py` | `scripts/clickhouse/export_clickhouse_source.py` |

推荐优先用 wrapper，因为 wrapper 会自动写入：

- `jobs/{SESSION_ID}/.meta/acquisition_log.jsonl`
- `jobs/{SESSION_ID}/.meta/artifact_index.json`
- `jobs/{SESSION_ID}/job_manifest.json`

原始导出和导出摘要默认登记为内部材料，不进入普通用户回复或报告输出清单。用户附件必须显式登记，不能靠文件名推断。

## 最小流程

```bash
# 1. 查 source
./scripts/py runtime/tableau/query_registry.py --search <keyword>
./scripts/py runtime/tableau/query_registry.py --source <source_id> --with-context

# 2A. Tableau 正式导出
./scripts/py skills/data-export/scripts/tableau/tableau_export_with_meta.py \
  --source-id <tableau_source_id> \
  --session-id $SESSION_ID \
  --vf "<filter>=<value>" \
  --reason "analysis data acquisition"

# 2B. DuckDB 正式导出
./scripts/py skills/data-export/scripts/duckdb/duckdb_export_with_meta.py \
  --source-id <duckdb_source_id> \
  --session-id $SESSION_ID \
  --output-name export.csv \
  --select "field_a,field_b" \
  --reason "analysis data acquisition"

# 2C. MySQL / ClickHouse 正式导出
./scripts/py skills/data-export/scripts/mysql/mysql_export_with_meta.py \
  --source-id <mysql_source_id> \
  --session-id $SESSION_ID \
  --output-name export.csv \
  --select "field_a,field_b" \
  --reason "analysis data acquisition"

./scripts/py skills/data-export/scripts/clickhouse/clickhouse_export_with_meta.py \
  --source-id <clickhouse_source_id> \
  --session-id $SESSION_ID \
  --output-name export.csv \
  --select "field_a,field_b" \
  --reason "analysis data acquisition"
```

## 参考资料

- Tableau 参考文档在 `references/tableau/`。
- DuckDB 输出契约在 `references/duckdb/`；MySQL / ClickHouse 使用同一 SQL export summary 契约。
- 用户只需要记住一个正式取数入口：`RA:data-export`。
