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

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 已注册数据源的 `source_id`、registry 查询结果、取数字段、过滤条件、`SESSION_ID`、导出原因和用户明确要求的附件范围。 |
| 输出 | 正式 CSV 数据文件、`export_summary`、采集记录、artifact index 更新和 `job_manifest` 更新。原始导出默认是内部证据，只有显式登记为用户附件时才进入用户输出。 |
| 下一步 | 将正式 CSV 交给 `RA:data-profile` 生成数据画像，再进入 `RA:analysis-plan` / `RA:report`。 |

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

## 内部脚本

后端入口（上表的 wrapper 与直接脚本）背后还有一组内部模块，一般不单独调用：

| 脚本 | 角色 |
| --- | --- |
| `scripts/sql/common_sql_export.py` | DuckDB / MySQL / ClickHouse 共用的 SQL 导出基类 |
| `scripts/tableau/_bootstrap.py` | 定位 workspace 根目录的内部 helper |
| `scripts/tableau/auth.py` | Tableau 认证模块（被 `export_source.py` / `export.py` / `list.py` import） |
| `scripts/tableau/export.py` | Tableau 视图导出与 long→wide 透视实现 |
| `scripts/tableau/list.py` | 列出可用 Tableau 视图 |
| `scripts/tableau/build_tableau_report_dashboard.py` | 生成 Tableau 报告 dashboard HTML 的工具 |
| `scripts/tableau/tableau_enrich_runtime_metadata.py` | 补齐 Tableau runtime metadata 缺失字段的维护工具 |
