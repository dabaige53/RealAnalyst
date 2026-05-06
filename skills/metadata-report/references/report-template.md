# Metadata Report Template

本模板是 `RA:metadata-report` 的目标报告结构，用于人工补写、审阅、迁移和检查脚本输出是否易读。正式生成入口仍是 `skills/metadata-report/scripts/generate_report.py`；当前 Python 渲染器若尚未改造，应以本模板作为后续脚本改版目标。

## Unified Structure

`````markdown
# {display_name} 元数据报告

## 1. 数据源结论

| 项目 | 内容 |
| --- | --- |
| 数据源 | {display_name} |
| 数据类型 | {connector} / {object_kind_or_view_type} |
| 当前状态 | {可用 / 可用但有待确认 / 暂不建议用于正式分析} |
| 数据规模 | {row_count_or_export_scope}，{field_count} 个字段，{metric_count} 个指标，{filter_count} 个筛选入口 |
| 主要用途 | {business_use_summary} |
| 不能用于 | {not_suitable_summary} |
| 最大风险 | {primary_risk_summary} |
| 待确认项 | {review_field_count} 个字段，{review_metric_count} 个指标，{review_filter_count} 个筛选器/参数 |

本报告说明这份数据源的 metadata 设计、来源依据、可用字段、指标口径、筛选方式和待确认问题。它不输出经营分析结论，只说明这份数据“能怎样被可靠使用”。

## 2. 业务适用场景

### 2.1 可以直接支持

| 场景 | 可用依据 | 使用提醒 |
| --- | --- | --- |
| {supported_scenario} | {fields_metrics_filters_used} | {usage_note} |

### 2.2 可以使用，但需要先确认口径

| 场景 | 当前缺口 | 确认后可支持什么 |
| --- | --- | --- |
| {conditional_scenario} | {review_gap} | {future_use} |

### 2.3 不建议用于

| 场景 | 原因 |
| --- | --- |
| {unsupported_scenario} | {reason} |

## 3. 核心字段与指标速查

### 3.1 常用字段

| 名称 | 类型 | 业务含义 | 常见用途 | 口径状态 | 使用提醒 |
| --- | --- | --- | --- | --- | --- |
| {display_name} | {时间/维度/属性/标识} | {business_definition} | {usage} | {已确认/待确认/仅结构可用} | {note} |

### 3.2 常用指标

| 指标 | 业务含义 | 计算或聚合方式 | 单位 | 适用粒度 | 口径状态 | 使用提醒 |
| --- | --- | --- | --- | --- | --- | --- |
| {metric_name} | {business_definition} | {expression_or_aggregation} | {unit} | {grain} | {已确认/待确认} | {note} |

## 4. 筛选方式与常用入口

| 筛选入口 | 类型 | 示例值/规则 | 使用方式 | 使用提醒 |
| --- | --- | --- | --- | --- |
| {filter_name} | {日期/地区/航线/组织/状态/参数} | {sample_values_or_rule} | {business_usage} | {note} |

说明：

- 示例值只用于帮助识别字段值域，不代表完整枚举。
- Tableau 报告必须区分筛选器 `--vf` 和参数 `--vp`。
- DuckDB 报告正文只写业务筛选入口；具体 `sql_where` 写法放到第 8 章。

## 5. 重点口径确认清单

| 优先级 | 主题 | 影响 | 当前问题 | 建议确认对象/材料 | 确认后用途 |
| --- | --- | --- | --- | --- | --- |
| 高 | {topic} | {impact} | {question} | {owner_or_evidence} | {future_use} |

写作要求：

- 不按内部字段名堆列表，按业务主题组织，例如收入、人数、载运率、耗油、预算版本、日期范围。
- 能说明影响范围时，写清会影响哪些分析场景。
- 不能确认的字段或指标，不写成确定业务口径。

## 6. 数据边界与风险

| 边界/风险 | 说明 | 对使用者的影响 |
| --- | --- | --- |
| {boundary_name} | {boundary_detail} | {business_impact} |

必须覆盖：

- 数据是实际完成值、计划值、预算值、还是 Tableau 已发布视图口径。
- 样本值、筛选值和导出字段是否来自真实采样或导出验证。
- 未确认字段、未确认指标、校验失败项对正式分析的限制。
- 当前报告能证明什么，不能证明什么。

## 7. 完整字段与指标明细

### 7.1 字段明细

| 名称 | 源字段 | 类型 | 角色 | 业务定义 | 示例/规则 | 口径状态 | 来源摘要 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {display_name} | {source_field} | {metadata_type} | {role} | {business_definition} | {sample_or_rule} | {confirmed_or_pending} | {evidence_summary} |

### 7.2 指标明细

| 指标 | 源字段/表达式 | 聚合方式 | 单位 | 业务定义 | 适用粒度 | 口径状态 | 来源摘要 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {metric_name} | {source_or_expression} | {aggregation} | {unit} | {business_definition} | {grain} | {confirmed_or_pending} | {evidence_summary} |

### 7.3 筛选器/参数明细

| 名称 | 类型 | 字段/参数 | 可选值/规则 | 是否必填 | 口径状态 | 来源摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| {name} | {filter_or_parameter} | {source_field_or_parameter} | {values_or_rule} | {required} | {confirmed_or_pending} | {evidence_summary} |

如果字段或指标数量过多，正文可以只保留核心字段/指标速查，本章仍必须保留完整明细。

## 8. Connector 使用说明

### 8.1 DuckDB 使用说明

仅 DuckDB 报告填写本节；Tableau 报告写“无”。

| 项目 | 值 |
| --- | --- |
| DuckDB 文件 | `{db_path}` |
| Schema | `{schema}` |
| 对象 | `{object_name}` |
| 对象类型 | `{object_kind}` |
| 查询边界 | {readonly_sampling_or_query_boundary} |

常用筛选写法：

| 业务筛选 | DuckDB 条件示例 | 注意事项 |
| --- | --- | --- |
| {filter_name} | `{sql_where}` | {note} |

### 8.2 Tableau 使用说明

仅 Tableau 报告填写本节；DuckDB 报告写“无”。

| 项目 | 值 |
| --- | --- |
| Workbook | `{workbook_name}` |
| View | `{view_name}` |
| View LUID | `{view_luid}` |
| Content URL | `{content_url}` |
| 页面 URL | `{page_url}` |
| 导出验证 | {export_validation_status} |

筛选器必须使用 `--vf`，参数必须使用 `--vp`。

| 类型 | 名称 | 示例 | 用途 |
| --- | --- | --- | --- |
| 筛选器 | {filter_name} | `--vf "{filter_name}={value}"` | {purpose} |
| 参数 | {parameter_name} | `--vp "{parameter_name}={value}"` | {purpose} |

推荐导出命令：

```bash
python3 {baseDir}/skills/data-export/scripts/tableau/export_source.py \
  --source-id {source_id} \
  --vp "{parameter_name}={parameter_value}" \
  --vf "{filter_name}={filter_value}"
```

## 9. 技术维护附录

### 9.1 注册与生成信息

| 项目 | 值 |
| --- | --- |
| `source_id` / `dataset_id` | `{source_id}` |
| `key` | `{key}` |
| `type` | `{type}` |
| `status` | `{status}` |
| 报告生成时间 | `{generated_at}` |
| 默认报告目录 | `metadata/sync/{connector}/reports/` |
| 执行链路 | `{metadata_yaml / validate / generate_report / sync_registry / export_validate}` |
| 步骤状态 | `{step_status}` |

### 9.2 Metadata 来源

| 来源 | 用途 | 状态 |
| --- | --- | --- |
| `metadata/datasets/*.yaml` | 数据集、字段、指标、粒度和适用边界 | {status} |
| `metadata/mappings/*.yaml` | 源字段到标准语义的映射和 review 状态 | {status} |
| `metadata/dictionaries/*.yaml` | 公共指标、维度和术语定义 | {status} |
| `metadata/sources/` | 原始证据、发现结果、用户说明和样本画像 | {status} |
| runtime registry / export manifest | 运行时可用性或导出验证 | {status} |

### 9.3 映射明细

| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 维护说明 |
| --- | --- | --- | --- | --- |
| {source_field} | {metric/dimension/field} | {standard_id} | {field_id_or_override} | {maintenance_note} |

### 9.4 校验结果

| 校验项 | 结果 | 说明 |
| --- | --- | --- |
| {validation_item} | {pass/fail/skipped} | {detail} |

## 10. 结论

- 这份 {connector} metadata 当前状态：{ready_status}。
- 可以优先用于：{primary_supported_use}。
- 暂不应用于：{primary_unsupported_use}。
- 下一步需要确认：{top_review_items}。
`````
