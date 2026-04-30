# Metadata Report Template

本模板来自 Analyst workspace 的 `tableau-sync` / `duckdb-sync` 报告脚本范式。正式生成时优先使用 `generate_sync_report.py`；本文件用于人工补写、审阅、迁移或检查报告是否完整。

## Tableau 数据源元数据报告模板

`````markdown
# Tableau Sync Report

## 1. 同步任务概览

- 报告类型：Tableau 数据源同步明细报告
- 报告生成时间：{generated_at}
- 同步对象：`{source_id}`
- 显示名称：`{display_name}`
- 原始链接：`{page_url}`
- 默认报告目录：`metadata/sync/tableau/reports/`
- 本次执行链路：`register` -> `sync_fields` -> `sync_filters` -> `sync_registry`
- 同步模式：`{live|dry-run}`
- 是否采集样例值：{是|否}
- 步骤状态：fields={status}, filters={status}, registry={status}

## 2. 数据源注册信息

| 项目 | 值 |
| --- | --- |
| `source_id` | `{source_id}` |
| `key` | `{key}` |
| `display_name` | `{display_name}` |
| `type` | `{view|domain}` |
| `status` | `{active|deprecated}` |
| `category` | `{category}` |
| `view_luid` | `{view_luid}` |
| `view_name` | `{view_name}` |
| `content_url` | `{content_url}` |
| `workbook_id` | `{workbook_id}` |
| `workbook_name` | `{workbook_name}` |
| `description` | `{description 或 当前 registry 内为空，尚未固化业务描述}` |

## 3. 本次写入摘要

### 3.1 注册层

- 当前 registry 条目状态：`{status}`
- 当前 spec 更新时间：`{updated}`
- 仍为空的注册信息：
- `{field_name}`

### 3.2 字段层

- 当前维度数：`{dimension_count}`
- 当前指标数：`{measure_count}`
- 合并后逻辑字段总数：`{logical_field_count}`
- 是否采样维度样例值：{是|否}

### 3.3 筛选器与参数层

- 当前筛选器数：`{filter_count}`
- 当前参数数：`{parameter_count}`
- 当前仍未固化 validation 的对象：
- `{filter_or_parameter}`

### 3.4 语义层

- 当前 `primary_dimensions`：`{count}`
- 当前 `available_metrics`：`{count}`
- 指标标准映射：`{mapped}/{total}` 已映射
- 维度标准映射：`{mapped}/{total}` 已映射
- 未解析维度：
- `{dimension_name}`

## 4. 建议补充的业务描述

以下内容是为了便于后续使用而生成的人类可读描述，默认不直接回写 registry：

> {one_paragraph_business_description}

### 4.1 补充计算字段说明

- `{field_name}`：{description}

## 5. 逻辑字段明细

| 逻辑字段 | 角色 | 数据类型 | 映射状态 | 标准映射/解释 | 描述来源 | 样例值/备注 |
| --- | --- | --- | --- | --- | --- | --- |
| `{field}` | 维度 | `{data_type}` | `{mapped|unresolved}` | {explanation} | {source} | {sample_values} |
| `{field}` | 指标 | `{data_type}` | `{mapped|unresolved}` | 标准指标 `{metric_id}` / {name_cn} / `{unit}` | 标准映射 | {definition} |

## 6. 筛选器明细

### 6.1 筛选器使用总则

- 本条数据源的筛选器使用 `--vf`
- 本条数据源的参数使用 `--vp`
- 样例值来自同步时采样，不代表完整可选集
- 当前筛选器若未固化 `validation`，使用时应优先参考样例值和实际验证

### 6.2 筛选器清单

| 筛选器 key | Tableau 字段 | 当前类型 | 推荐传参方式 | 示例命令片段 | 使用建议 |
| --- | --- | --- | --- | --- | --- |
| `{field}` | `{tableau_field}` | `{kind}` | `--vf` | `--vf "{field}={value}"` | {suggestion} |

### 6.3 筛选器样例值

#### `{field}`

当前采样到的值：

- `{value}`

## 7. 参数明细

### 7.1 参数使用总则

- 参数必须使用 `--vp`
- 不要把日期参数误传成 `--vf`
- 若当前未固化 validation，默认推荐使用 `YYYY-MM-DD`

### 7.2 参数清单

| 参数 key | Tableau 字段 | 推荐格式 | 传参方式 | 示例 | 用途说明 | 当前校验状态 |
| --- | --- | --- | --- | --- | --- | --- |
| `{parameter}` | `{tableau_field}` | `YYYY-MM-DD` | `--vp` | `--vp "{parameter}=2026-01-01"` | {purpose} | {validation_status} |

### 7.3 推荐使用方式

```bash
python3 {baseDir}/skills/data-export/scripts/tableau/export_source.py \
  --source-id {source_id} \
  --vp "{date_start}=2026-01-01" \
  --vp "{date_end}=2026-01-31" \
  --vf "{filter_field}={filter_value}"
```

## 8. 指标与维度映射结果

### 8.1 已映射指标

| 源字段 | 标准指标ID | 标准名称 | 单位 | 说明 |
| --- | --- | --- | --- | --- |
| `{source_field}` | `{metric_id}` | {name_cn} | `{unit}` | {definition} |

### 8.2 尚未标准化的维度

| 源字段 | 当前状态 | 建议解释 | 备注 |
| --- | --- | --- | --- |
| `{source_field}` | `{status}` | {suggestion} | 建议后续补维度映射或别名 |

## 9. 导出验证与结构差异

### 9.1 可用导出产物

- `export_summary.json`：{path}
- `manifest.json`：{path}

### 9.2 字段结构核对

- registry/spec 中逻辑可用字段共 `{logical_count}` 个
- 实际导出的 CSV 物理列共 `{physical_count}` 个

### 9.3 需要特别说明的结构差异

- {difference_note}

## 10. 本条数据源的结论

- 这条 Tableau 数据源已登记为 `{source_id}`
- 当前 metadata / spec / semantics 已完成同步
- 指标语义映射状态：{summary}
- 维度标准化状态：{summary}
- 时间控制建议优先通过 `{parameter_names}` 等参数完成
- 离散筛选建议通过 `--vf` 使用本报告中列出的字段和样例值
`````

## DuckDB 数据源元数据报告模板

`````markdown
# DuckDB Sync Report

## 1. 同步任务概览

- 报告类型：DuckDB 元数据注册/同步明细报告
- 报告生成时间：{generated_at}
- 同步对象：`{source_id}`
- 显示名称：`{display_name}`
- 默认报告目录：`metadata/sync/duckdb/reports/`
- 本次执行链路：`register` -> `sync_registry` -> `validate` -> `generate_sync_report`
- 同步模式：`{live|dry-run}`
- 步骤状态：register={status}, registry={status}, validate={status}

## 2. 数据源注册信息

| 项目 | 值 |
| --- | --- |
| `source_id` | `{source_id}` |
| `key` | `{key}` |
| `type` | `{duckdb_view|duckdb_table}` |
| `status` | `{status}` |
| `category` | `{category}` |
| `display_name` | `{display_name}` |
| `description` | `{description}` |
| `db_path` | `{db_path}` |
| `schema` | `{schema}` |
| `object_name` | `{object_name}` |
| `object_kind` | `{view|base table}` |

## 3. 本次写入摘要

- 字段总数：`{field_count}`
- 维度数：`{dimension_count}`
- 指标数：`{measure_count}`
- 筛选器数：`{filter_count}`
- 粒度字段数：`{grain_count}`
- 时间字段数：`{time_field_count}`
- 示例值采样字段数：`{sampled_field_count}`

## 4. 语义层明细

### 4.1 粒度

- `{grain_field}`

### 4.2 时间字段

- `{time_field}`

### 4.3 适用场景

- {suitable_for}

### 4.4 不适用场景

- {not_suitable_for}

## 5. 字段明细

| 展示名 | 源字段 | DuckDB 类型 | metadata 类型 | 角色 | 业务定义 | 定义来源 | 示例值 | 证据 | Review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `{display_name}` | `{source_field}` | `{duckdb_type}` | `{metadata_type}` | `{role}` | `{definition}` | `{definition_source}` | `{sample_values}` | `{evidence}` | `{review}` |

## 6. 指标明细

| 指标 | 源字段 | 表达式 | 聚合方式 | 单位 | 业务定义 | 证据 | Review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `{metric}` | `{source_field}` | `{expression}` | `{aggregation}` | `{unit}` | `{definition}` | `{evidence}` | `{review}` |

## 7. 筛选器明细

DuckDB 数据源没有 Tableau 参数；后续取数筛选应通过 `sql_where` 或 data-export 的 DuckDB 筛选参数表达。

> 示例值为报告生成时从 DuckDB 当前对象中只读抽取的非空样本，不代表完整枚举清单；正式筛选仍以实时数据和业务口径为准。

| 字段 | 显示名 | 应用方式 | 可选值/示例 | 说明 |
| --- | --- | --- | --- | --- |
| `{field}` | `{display_name}` | `sql_where` | `{sample_values}` | 按 `{field}` 过滤；示例值来自 DuckDB 当前非空样本，正式取数仍以实时数据为准 |

## 8. 映射与 Review 问题

### 8.1 已注册映射

| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 说明 |
| --- | --- | --- | --- | --- |
| `{view_field}` | `{metric|dimension}` | `{standard_id}` | `{field_id_or_override}` | `{definition_or_notes}` |

### 8.2 待确认问题

- 待确认字段：`{review_field_count}` 个
- 待确认指标：`{review_metric_count}` 个
- `{pending_question}`

## 9. 校验结果

- {validate_result_sentence}

## 10. 本条数据源的结论

- 这条 DuckDB 数据源已登记为 `{source_id}`
- 当前 metadata YAML 已完成注册报告生成
- `registry.db` 不作为业务口径真源；如需要进入运行取数层，先使用 `RA:metadata` 的 `sync-registry`
`````

## 使用规则

1. 脚本输出是正式底稿；模板用于人工补全，不要反过来覆盖脚本事实。
2. Tableau 必须保留筛选器 `--vf` 和参数 `--vp` 的区别。
3. DuckDB 必须保留 `db_path`、`schema`、`object_name`、`object_kind`，方便后续追溯真实对象。
4. DuckDB 示例值必须来自只读采样；采样失败时写清原因，例如“未采样：DuckDB Python 模块不可用 / 数据库不可访问 / 字段不存在”。
5. 所有 `{placeholder}` 都必须替换；没有事实时写“未配置 / 待确认”，不要留占位符。
6. 低置信度、缺 validation、未解析维度、逻辑字段与物理列差异，必须写入报告正文。
