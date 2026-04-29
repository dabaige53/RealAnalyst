---
name: data-export
description: |
  Controlled Tableau and DuckDB data export for RealAnalyst/Codex. Use when an analysis task needs to fetch formal CSV data from a registered source in the unified SQLite registry, including Tableau view/domain exports with vf/vp filters and DuckDB table/view exports with field whitelist, filters, aggregation, and audited metadata write-back. Triggers: tableau export, duckdb export, 受控取数, 数据导出, 补数, 追加分析, export_summary, duckdb_export_summary.
---

# Data Export Skill

统一处理 RealAnalyst 的正式取数：Tableau 与 DuckDB 都必须从已注册的 runtime registry 中选择 source，导出到 `jobs/{SESSION_ID}/data/*.csv`，并写回审计元数据。

本 skill 是原 `tableau-export` 与 `duckdb-export` 的合并版。原脚本保留在后端子目录中：

- Tableau: `skills/data-export/scripts/tableau/`
- DuckDB: `skills/data-export/scripts/duckdb/`

## 通用硬规则

1. 先用 `runtime/tableau/query_registry.py` 搜索、锁定并确认 source，不要自由拼接连接信息。
2. 只允许导出 registry/spec 中已注册、`status=active` 的 source。
3. 正式输出必须写入 `jobs/{SESSION_ID}/`，不要把正式 CSV 写到临时目录后再口头引用。
4. 连续分析中继续使用同一个 `SESSION_ID`；补同一 source 的数据可以直接执行，但要写明原因。
5. 引入新 source 前必须获得用户确认，并在 acquisition log 中标记 `--is-new-source --confirmed`。
6. 导出后优先使用 wrapper 脚本，因为 wrapper 会同步更新 `.meta/acquisition_log.jsonl` 与 `.meta/artifact_index.json`。

## Step 1：查询 registry

```bash
./scripts/py runtime/tableau/query_registry.py --search <keyword>
./scripts/py runtime/tableau/query_registry.py --source <source_id> --with-context
./scripts/py runtime/tableau/query_registry.py --filter <source_id>
./scripts/py runtime/tableau/query_registry.py --fields <source_id>
```

读取 `source_backend` 后再进入对应后端流程。

## Tableau 后端

### 推荐入口

```bash
./scripts/py skills/data-export/scripts/tableau/tableau_export_with_meta.py \
  --source-id <tableau_source_id> \
  --session-id $SESSION_ID \
  --vf "<filter_field>=<value>" \
  --vp "<parameter_field>=<value>" \
  --reason "<why this export is needed>"
```

### 直接导出入口（仅排障）

```bash
./scripts/py skills/data-export/scripts/tableau/export_source.py \
  --source-id <tableau_source_id> \
  --session-id $SESSION_ID \
  --vf "<filter_field>=<value>" \
  --vp "<parameter_field>=<value>"
```

### Tableau 参数规则

- `filters:` 中定义的项用 `--vf`。
- `parameters:` 中定义的项用 `--vp`。
- `type: view`：只传 `--source-id`。
- `type: domain`：传 `--source-id <domain_source_id> --views <view_id,...>`。
- 枚举型筛选字段支持多选时，可在单次 `--vf` 中用逗号传多个值。

详细说明按需读取：

- `references/tableau/export-modes.md`
- `references/tableau/filter-usage.md`
- `references/tableau/filters-fallback.md`
- `references/tableau/budget-and-recovery.md`

## DuckDB 后端

### 推荐入口

```bash
./scripts/py skills/data-export/scripts/duckdb/duckdb_export_with_meta.py \
  --source-id <duckdb_source_id> \
  --session-id $SESSION_ID \
  --output-name <name>.csv \
  --select "field_a,field_b" \
  --filter "region=East" \
  --reason "<why this export is needed>"
```

### 聚合示例

```bash
./scripts/py skills/data-export/scripts/duckdb/duckdb_export_with_meta.py \
  --source-id <duckdb_source_id> \
  --session-id $SESSION_ID \
  --output-name revenue_by_region.csv \
  --group-by "region" \
  --aggregate "revenue:sum:total_revenue" \
  --order-by "total_revenue:desc"
```

### 直接导出入口（仅排障）

```bash
./scripts/py skills/data-export/scripts/duckdb/export_duckdb_source.py \
  --source-id <duckdb_source_id> \
  --session-id $SESSION_ID \
  --output-name <name>.csv \
  --select "field_a,field_b"
```

### DuckDB 安全边界

- 只能使用注册字段做 `--select`、`--filter`、`--date-range`、`--group-by`、`--aggregate`、`--order-by`。
- 过滤语法仅支持 `field=value`、`field!=value`、`field~keyword`。
- 聚合函数仅支持 `sum`、`avg`、`min`、`max`、`count`。
- 禁止导出 `TEMP_`、`ToDrop_` 等临时/废弃对象。

完整输出契约见 `references/duckdb/output-contract.md`。

## 输出契约

Tableau wrapper 成功后通常产生：

- `jobs/{SESSION_ID}/data/交叉_<source_or_view>.csv`
- `jobs/{SESSION_ID}/export_summary.json`
- `jobs/{SESSION_ID}/source_context.json`
- `jobs/{SESSION_ID}/context_injection.md`
- `jobs/{SESSION_ID}/.meta/acquisition_log.jsonl`
- `jobs/{SESSION_ID}/.meta/artifact_index.json`

DuckDB wrapper 成功后通常产生：

- `jobs/{SESSION_ID}/data/<output-name>.csv`
- `jobs/{SESSION_ID}/duckdb_export_summary.json`
- `jobs/{SESSION_ID}/.meta/acquisition_log.jsonl`
- `jobs/{SESSION_ID}/.meta/artifact_index.json`

## 验证

```bash
./scripts/py skills/data-export/scripts/tableau/export_source.py --help
./scripts/py skills/data-export/scripts/tableau/tableau_export_with_meta.py --help
./scripts/py skills/data-export/scripts/duckdb/export_duckdb_source.py --help
./scripts/py skills/data-export/scripts/duckdb/duckdb_export_with_meta.py --help
./scripts/py skills/data-export/scripts/duckdb/run_tests.py
```

`run_tests.py` 需要先安装 `duckdb` 并准备 demo DuckDB registry/data。若未准备 DuckDB 文件，帮助命令仍应能跑通，但正式导出会失败。
