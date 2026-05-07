# 元数据报告模板

本模板是 `RA:metadata-report` 的 dataset-first 输出契约，用于人工审阅和检查脚本输出是否易读。正式生成入口是 `skills/metadata-report/scripts/generate_report.py`。

## Dataset-first 统一结构

`````markdown
# {数据源名称} 元数据报告

## 1. 元数据事实摘要

| 项目 | 内容 | 来源 |
| --- | --- | --- |
| 数据集 | {数据源名称} | metadata/datasets |
| 系统标识 | {dataset_id} | metadata/datasets |
| 连接器 | {connector} | metadata/datasets |
| 字段数 | {field_count} | metadata/datasets |
| 指标数 | {metric_count} | metadata/datasets |
| 注册状态 | {已注册 / 未注册} | runtime/registry |

## 2. 数据集信息

| 项目 | 内容 | 来源 |
| --- | --- | --- |
| 展示名称 | {display_name} | metadata/datasets |
| 业务说明 | {description / 未维护} | metadata/datasets |
| 业务域 | {domain / 未维护} | metadata/datasets |
| 分析粒度 | {grain / 未维护} | metadata/datasets |
| 主键 | {primary_key / 未维护} | metadata/datasets |
| 时间字段 | {time_fields / 未维护} | metadata/datasets |
| 适用场景 | {suitable_for / 未维护} | metadata/datasets |
| 不适用场景 | {not_suitable_for / 未维护} | metadata/datasets |

## 3. 字段信息

| 名称 | 系统标识 | 物理字段 | 角色 | 类型 | 业务定义 | 定义来源 | 状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {字段展示名} | {field.name} | {source_field} | {role} | {type} | {business_definition.text / 未维护} | {ref/source_type / 未维护} | {已维护 / 待补齐 / 未维护} | metadata/datasets/{dataset_id}.yaml::fields[name={字段名}].business_definition |

## 4. 指标信息

| 指标 | 系统标识 | 表达式 | 聚合方式 | 单位 | 适用粒度 | 业务定义 | 定义来源 | 状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {指标名称} | {metric.name} | {expression} | {aggregation / 未维护} | {unit / 未维护} | {valid_grains / 未维护} | {business_definition.text / 未维护} | {ref/source_type / 未维护} | {已维护 / 待补齐 / 未维护} | metadata/datasets/{dataset_id}.yaml::metrics[name={指标名}].business_definition |

## 5. 筛选、参数与取值信息

| 名称 | 类型 | 取值类型 | 已维护取值或范围 | 使用方式 | 来源 |
| --- | --- | --- | --- | --- | --- |
| {筛选入口名称} | {时间字段/筛选字段/参数} | {取值列表/数值范围/日期范围} | {values/range/未维护} | {sql_where / --vf / --vp} | runtime/registry |

## 6. 映射与来源追溯

| 来源文件 | 源字段 | 类型 | 标准语义 | 本地字段 | 说明 |
| --- | --- | --- | --- | --- | --- |
| metadata/mappings/{mapping}.yaml | {view_field} | {type} | {standard_id} | {field_id_or_override} | {notes / 未维护} |

## 7. 未维护项

| 对象 | 类型 | 缺口 | 位置 |
| --- | --- | --- | --- |
| {字段/指标/筛选/数据集} | {字段/指标/注册状态} | {business_definition 未维护 / 取值或范围未维护 / 未注册} | {metadata path / runtime registry path} |

## 8. 运行与注册状态

| 项目 | 状态 | 来源 |
| --- | --- | --- |
| metadata YAML | 已维护 | metadata/datasets/{dataset_id}.yaml |
| metadata index | {已维护 / 未维护} | metadata/index |
| runtime registry | {已注册 / 未注册} | runtime/registry.db |
| runtime spec | {已维护 / 未维护} | runtime/registry.db |

## 9. 报告生成信息

| 项目 | 内容 |
| --- | --- |
| 生成时间 | {generated_at} |
| 生成入口 | skills/metadata-report/scripts/generate_report.py |
| 读取入口 | skills/metadata/lib/metadata_facts.py |
| 默认输出目录 | metadata/reports |
`````

报告不生成 JSON context sidecar；agent 结构化读取统一使用 `metadata.py read/search/status`。
