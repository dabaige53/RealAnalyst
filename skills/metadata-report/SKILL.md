---
name: "RA:metadata-report"
description: |
  Use when generating Markdown reports that explain RealAnalyst metadata, sync results, dataset registration details, field/metric/filter semantics,
  metadata gaps, or metadata inventory. Triggers: 元数据报告, 同步结果说明, 字段口径说明, 数据集注册报告, 元数据清单.
---

# Metadata Report Skill

用于把 RealAnalyst 的元数据、连接器同步结果、数据源注册信息和待补齐项写成可复核的 Markdown 报告。它只负责“阐述元数据”，不负责注册数据集、取数分析或改写业务结论。

本 skill 是元数据 Markdown 报告的唯一出口。报告统一通过 `skills/metadata-report/scripts/generate_report.py` 生成；DuckDB 和 Tableau 共享“数据源结论 -> 适用场景 -> 核心字段/指标 -> 筛选入口 -> 元数据补齐清单 -> 完整明细 -> 技术附录”的阅读骨架，但数据源调用信息必须按连接器分别写清。

## When to Use

使用本 skill：

- 用户要求生成、补齐或解释元数据 Markdown 报告。
- 需要把数据集字段、指标、筛选器、参数、粒度、适用场景、不适用场景写成报告。
- 需要说明 Tableau / DuckDB 元数据报告中同步了什么、哪些字段进入元数据、哪些仍待补齐。
- 需要做元数据清单、注册结果说明、字段口径补齐清单或待补齐项报告。

不要使用本 skill：

- 需要维护 YAML、注册数据集、生成索引或上下文：使用 `RA:metadata`。
- 需要导出真实数据或做完整分析：普通用户进入 `RA:analysis-run`；仅高级手工编排或排障时由流程调用 `RA:data-export`。
- 需要写分析结论报告：使用 `RA:report`。
- 只需要验证分析报告质量：使用 `RA:report-verify`。

## Source Priority

报告只能基于真实元数据产物和脚本输出，禁止凭字段名想象业务含义。
字段和指标必须按通用结构处理：role、business_definition、expression、aggregation、mapping、dictionary、evidence、sample 和 validate 状态。禁止为了某个具体业务字段名、指标名或固定中文列名写特例补丁。

优先级如下：

1. `metadata/datasets/*.yaml`：数据集说明、字段、指标、时间字段、粒度、适用边界。
2. `metadata/mappings/*.yaml`：源字段到标准语义的映射和补齐状态。
3. `metadata/dictionaries/*.yaml`：公共指标、维度、术语的业务定义。
4. `metadata/sources/`：原始证据、用户文档、connector discovery 归档。
5. `metadata/sync/{tableau,duckdb}/reports/*.md`：连接器同步明细报告。
6. `runtime/registry.db` 或导出 registry 查询结果：只说明运行时是否可取数，不作为业务定义来源。

若同一含义在多处冲突，以 YAML 中带证据和补齐状态的业务定义为准；连接器字段名只能作为结构素材。

## 标准脚本入口

优先使用统一报告生成脚本，不手写从零拼报告。

| 报告类型 | 脚本 | 默认输出目录 |
| --- | --- | --- |
| Tableau 数据源元数据报告 | `skills/metadata-report/scripts/generate_report.py --connector tableau --dataset-id <dataset_id>` | `metadata/sync/tableau/reports/` |
| DuckDB 单数据集注册报告 | `skills/metadata-report/scripts/generate_report.py --connector duckdb --dataset-id <dataset_id>` | `metadata/sync/duckdb/reports/` |
| DuckDB 全量 YAML 注册报告 | `skills/metadata-report/scripts/generate_report.py --connector duckdb --all-yaml` | `metadata/sync/duckdb/reports/` |
| runtime registry 同步说明 | `skills/metadata-report/scripts/generate_report.py --connector <connector> --all` | `metadata/sync/{connector}/reports/` |

## 推荐工作流

### 1. 先确认元数据当前状态

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py inventory
python3 {baseDir}/skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
```

如果 `validate` 失败，报告必须把失败项写成“待修复问题”，不要把未通过校验的定义写成确定口径。

### 2. 优先生成或读取元数据报告

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata-report/scripts/generate_report.py --connector tableau --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata-report/scripts/generate_report.py --connector duckdb --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata-report/scripts/generate_report.py --connector duckdb --all-yaml
```

DuckDB 报告入口选择：

- `--dataset-id <dataset_id>`：首选。基于已维护的元数据 YAML 生成单个注册报告。
- `--all-yaml`：基于元数据 YAML 为全部 DuckDB dataset 生成注册报告。
- `--all`：只用于 runtime registry 同步说明，不作为业务口径来源。

如果已有元数据报告，优先读取最新报告；不要为了写说明重复同步外部系统。

### 3. 按标准模板补充说明

需要人工补写或审阅时，先读取：

```text
{baseDir}/skills/metadata-report/references/report-template.md
```

该模板是脚本输出结构的目标写作版；脚本若仍输出旧结构，以模板作为后续改造目标，人工补写时优先遵循模板。

## 报告结构

所有 connector 报告至少包含：

1. `## 1. 数据源结论`
2. `## 2. 业务适用场景`
3. `## 3. 核心字段与指标速查`
4. `## 4. 筛选方式与常用入口`
5. `## 5. 元数据补齐清单`
6. `## 6. 数据边界与风险`
7. `## 7. 完整字段与指标明细`
8. `## 8. 数据源使用说明`
9. `## 9. 技术维护附录`
10. `## 10. 结论`

正文只放分析师需要立刻理解的信息：能不能用、适合什么、不适合什么、关键字段/指标、筛选入口、主要待补齐项。完整字段、指标、筛选器、参数、映射、来源状态和校验结果必须保留，但放到第 7-9 章。

核心字段表推荐列，详见 `references/report-template.md`：

| 名称 | 类型 | 业务含义 | 口径状态 | 定义位置 |
| --- | --- | --- | --- | --- |

核心指标表推荐列：

| 指标 | 业务含义 | 计算或聚合方式 | 单位 | 适用粒度 | 口径状态 | 定义位置 |
| --- | --- | --- | --- | --- | --- | --- |

完整明细表可以保留源字段、表达式、示例值和定义位置。定义位置必须是相对 YAML 定位，例如 `metadata/datasets/<dataset_id>.yaml::fields[name=<name>].business_definition`；`business_definition.ref` 和 `metadata/audit` 只用于维护追溯，不进入核心字段/指标表。

DuckDB 报告中的示例值应从 DuckDB 当前对象只读采样得到；它们只用于帮助业务识别筛选写法和字段值域，不代表完整枚举清单，也不替代 YAML 中的业务定义。

## 写作规则

1. 先给“数据源结论”，再解释元数据如何支撑这个结论。
2. 正文不要堆内部映射、样本画像、证据路径和 registry 状态；这些内容放技术维护附录。
3. 字段、指标、筛选器、参数不能删；正文可精选，完整明细必须保留。
4. `needs_review=true`、`review_required=true` 或无证据项必须显式进入“元数据补齐清单”。
5. 不把 Tableau 参数写成普通筛选器；Tableau `filters` 和 `parameters` 必须分开说明。
6. 不把 DuckDB 表结构直接当业务口径；表结构只说明字段存在。
7. 不写泛泛总结；报告必须列出真实存在的字段、指标、筛选器、参数、适用/不适用场景；没有内容的 section 直接删除。
8. 报告是给分析师复核的，少写系统实现细节，多写口径、边界和调用方式。
9. Tableau 报告必须分清 `--vf` 筛选器和 `--vp` 参数；DuckDB 报告必须分清 `sql_where` 筛选器和字段/指标。
10. DuckDB YAML 模式下，`registry=not_written` 是正常状态；报告必须说明“未反写 registry，不把 registry.db 当业务口径来源”。
11. 不展示旧 YAML 的 `schema_note`，也不要生成“Schema 说明”列；字段存在性、DuckDB 类型、Tableau 字段名只能作为结构化类型或证据来源，不作为业务定义。
12. 不根据 role/status 自动生成字段或指标的“常见用途”“使用建议”；元数据没有显式维护时，核心表删除这些列。

## 质量门禁

完成前检查：

- 已说明元数据来源：dataset YAML、mapping、dictionary、source 或同步报告。
- 字段、指标、筛选器、参数没有混写。
- 所有不确定项都进入“元数据补齐清单”。
- 没有把未校验 YAML、connector 字段名或 runtime registry 写成确定业务定义。
- 输出路径符合报告类型，且 Markdown 能独立阅读。

## 常见误区

| 误区 | 正确做法 |
| --- | --- |
| 只写“已同步成功” | 列清同步对象、字段、指标、筛选器、参数和待补齐项 |
| 用字段名猜业务定义 | 只读取 `business_definition.text`；找不到就标记待补齐 |
| 把元数据报告写成分析报告 | 只说明元数据能力和边界，不输出业务经营结论 |
| 把 `schema_note` 当业务说明展示 | 报告只展示 `business_definition.text`、定义位置和口径状态 |
| 忽略筛选器枚举值 | 可列举值、默认值、参数用法必须单独写 |
| 遇到 validate 失败仍继续写确定口径 | 报告降级为“元数据待修复报告”，失败项进入元数据补齐清单 |

## Completion Summary

元数据报告完成后，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已生成报告类型：<元数据报告 / 注册说明 / 待补齐项报告>
- 报告输出路径：<path>
- 待补齐项：<needs_review / 校验失败项 / metadata gap 数量>

下一步建议：
- 最推荐下一步：/skill RA:analysis-run ...（metadata 和 registry 已准备好，准备正式分析）
- 可选下一步：/skill RA:metadata ...（需要修复待补齐项或维护 YAML）
- 可选下一步：/skill RA:metadata-refine ...（需要把分析反馈整理为修正材料）

边界提醒：
- 本 skill 只生成数据集长期口径说明或 gap 报告，没有修改正式 metadata。
- 报告内容必须来自真实 metadata、connector 输出、export manifest、sample profile、mapping 或 dictionary evidence。
```
