# Metadata Report Template

本模板是 `RA:metadata-report` 的统一报告结构。正式生成时优先使用 `skills/metadata-report/scripts/generate_report.py`；本文件用于人工补写、审阅、迁移或检查报告是否完整。

## 统一结构

`````markdown
# {display_name} 注册报告

## 1. 同步任务概览

- 报告类型：{connector} 元数据注册/同步明细报告
- 报告生成时间：{generated_at}
- 同步对象：`{dataset_id}`
- 显示名称：`{display_name}`
- 默认报告目录：`metadata/sync/{connector}/reports/`
- 本次执行链路：{metadata_yaml / sync_fields / sync_filters / sync_registry / validate / generate_report}
- 同步模式：`{live|dry-run|metadata-yaml}`
- 步骤状态：{step_status}
- metadata YAML：{已读取|未找到}

## 2. 数据源注册信息

| 项目 | 值 |
| --- | --- |
| `source_id` | `{source_id}` |
| `key` | `{key}` |
| `type` | `{type}` |
| `status` | `{status}` |
| `category` | `{category}` |
| `display_name` | `{display_name}` |
| `description` | `{description}` |
| `{connector_specific_key}` | `{connector_specific_value}` |

## 3. 本次写入摘要

- 字段总数：`{field_count}`
- 维度数：`{dimension_count}`
- 指标数：`{metric_count}`
- 筛选器数：`{filter_count}`
- 参数数：`{parameter_count}`
- mapping 条目数：`{mapping_count}`
- 待确认字段数：`{review_field_count}`
- 待确认指标数：`{review_metric_count}`

## 4. 语义层明细

### 4.1 业务描述

> {business_description}

### 4.2 粒度

- `{grain_field}`

### 4.3 时间字段 / 参数

- `{time_field_or_parameter}`

### 4.4 适用场景

- {suitable_for}

### 4.5 不适用场景

- {not_suitable_for}

## 5. 字段明细

| 展示名 | 源字段 | 源类型 | metadata 类型 | 角色 | 业务定义 | 定义来源 | 示例/规则 | 证据 | Review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `{display_name}` | `{source_field}` | `{source_type}` | `{metadata_type}` | `{role}` | `{definition}` | `{definition_source}` | `{sample_or_regex}` | `{evidence}` | `{review}` |

## 6. 指标明细

| 指标 | 源字段 | 表达式 | 聚合方式 | 单位 | 业务定义 | 定义来源 | 证据 | Review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `{metric}` | `{source_field}` | `{expression}` | `{aggregation}` | `{unit}` | `{definition}` | `{definition_source}` | `{evidence}` | `{review}` |

## 7. 筛选器明细

| 字段 | 显示名 | 应用方式 | 可选值/示例/规则 | 说明 |
| --- | --- | --- | --- | --- |
| `{field}` | `{display_name}` | `{sql_where|--vf}` | `{sample_or_regex}` | `{usage_note}` |

{tableau_usage_section}

## {mapping_section_number}. 映射与 Review 问题

### {mapping_section_number}.1 已注册映射

| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 说明 |
| --- | --- | --- | --- | --- |
| `{view_field}` | `{metric|dimension|field}` | `{standard_id}` | `{field_id_or_override}` | `{definition_or_notes}` |

### {mapping_section_number}.2 待确认问题

- 待确认字段：`{review_field_count}` 个
- 待确认指标：`{review_metric_count}` 个
- `{pending_question}`

## {validation_section_number}. 校验结果

- {validate_result_sentence}
- {export_or_registry_boundary}

## {conclusion_section_number}. 本条数据源的结论

- 这条 {connector} 数据源已登记为 `{source_id}`
- 当前报告基于 metadata YAML、mapping YAML、source evidence 和必要 runtime 信息生成
- 带 `待确认` 标记的字段或指标不能直接作为最终确定口径
`````

## Tableau 专属章节

Tableau 报告在 `## 7. 筛选器明细` 后插入以下章节，其余结构不变，后续章节编号顺延：

`````markdown
## 8. Tableau 使用方式

Tableau 参数必须使用 `--vp`，不要把日期参数误传成 `--vf`。

| 参数 | 推荐格式 | 示例 | 用途 |
| --- | --- | --- | --- |
| `{parameter}` | `YYYY-MM-DD` | `--vp "{parameter}=2026-01-01"` | {purpose} |

推荐命令：

```bash
python3 {baseDir}/skills/data-export/scripts/tableau/export_source.py \
  --source-id {source_id} \
  --vp "{date_start}=2026-01-01" \
  --vp "{date_end}=2026-01-31" \
  --vf "{filter_field}={filter_value}"
```
`````

## 使用规则

1. `业务定义` 列只写已确认定义；未确认时统一写 `业务定义待确认`。
2. `定义来源` 未确认时统一写 `pending`，Review 写 `待确认（置信度 x）`。
3. Tableau 必须保留筛选器 `--vf` 和参数 `--vp` 的区别。
4. DuckDB 必须保留 `db_path`、`schema`、`object_name`、`object_kind`，方便追溯真实对象。
5. DuckDB 示例值必须来自只读采样；采样失败时写清原因。
6. 公式不能出现嵌套反引号；例如写 `Σ Cnf`，不要把字段名再单独包一层反引号。
7. 所有 `{placeholder}` 都必须替换；没有事实时写“未配置 / 待确认”，不要留占位符。
8. 不把 connector 字段名、runtime registry 或未校验 YAML 写成确定业务定义。
