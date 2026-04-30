---
name: "RA:metadata-report"
description: |
  Use when generating Markdown reports that explain RealAnalyst metadata, metadata sync results, dataset registration details, field/metric/filter semantics,
  review gaps, or metadata inventory. Triggers: 元数据报告, metadata markdown report, 同步报告说明, 字段口径说明, 数据集注册报告, metadata inventory.
---

# Metadata Report Skill

用于把 RealAnalyst 的 metadata、connector sync 结果、数据源注册信息和待 review 问题写成可复核的 Markdown 报告。它只负责“阐述元数据”，不负责注册数据集、取数分析或改写业务结论。

本 skill 的报告范式参考 Analyst workspace 的 `tableau-sync` / `duckdb-sync` 标准报告脚本：核心都是 `generate_sync_report.py` 中的 `render_*_report()`，先由脚本生成结构化 Markdown，再由 Agent 按业务语义补充说明和待确认问题。DuckDB 注册报告优先从 `metadata/datasets/*.yaml` 生成；只有需要解释 runtime 取数状态时才读取 registry。

## When to Use

使用本 skill：

- 用户要求生成、补齐或解释 metadata Markdown 报告。
- 需要把数据集字段、指标、筛选器、参数、粒度、适用场景、不适用场景写成报告。
- 需要说明 Tableau / DuckDB sync report 中同步了什么、哪些字段进入 metadata、哪些仍待确认。
- 需要做 metadata inventory、注册结果说明、字段口径审阅清单或 review gap 报告。

不要使用本 skill：

- 需要维护 YAML、注册数据集、生成 index/context：使用 `RA:metadata`。
- 需要导出真实数据：使用 `RA:data-export`。
- 需要写分析结论报告：使用 `RA:report`。
- 只需要验证分析报告质量：使用 `RA:report-verify`。

## Source Priority

报告只能基于真实 metadata 产物和脚本输出，禁止凭字段名想象业务含义。

优先级如下：

1. `metadata/datasets/*.yaml`：数据集说明、字段、指标、时间字段、粒度、适用边界。
2. `metadata/mappings/*.yaml`：源字段到标准语义的映射、置信度和 review 状态。
3. `metadata/dictionaries/*.yaml`：公共指标、维度、术语的业务定义。
4. `metadata/sources/`：原始证据、用户文档、connector discovery 归档。
5. `metadata/sync/{tableau,duckdb}/reports/*.md`：connector 同步明细报告。
6. `runtime/registry.db` 或导出 registry 查询结果：只说明运行时是否可取数，不当业务定义真源。

若同一含义在多处冲突，以 YAML 中带证据和 review 状态的业务定义为准；connector 字段名只能作为素材。

## 标准脚本入口

优先使用已有报告生成脚本，不手写从零拼报告。

| 报告类型 | 脚本 | 核心函数 | 默认输出目录 |
| --- | --- | --- | --- |
| Tableau 数据源元数据报告 | `skills/metadata/adapters/tableau/scripts/generate_sync_report.py` | `render_sync_report()` | `metadata/sync/tableau/reports/` |
| DuckDB YAML 注册报告 | `skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --dataset-id <dataset_id>` | `render_yaml_metadata_report()` | `metadata/sync/duckdb/reports/` |
| DuckDB registry 同步报告 | `skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --key <source_key>` | `render_sync_report()` | `metadata/sync/duckdb/reports/` |

Analyst 原始参考路径：

- Tableau：`.agents/skills/tableau-sync/scripts/generate_sync_report.py`，默认输出 `tableau_sync/`
- DuckDB：`.agents/skills/duckdb-sync/scripts/generate_sync_report.py`，默认输出 `duckdb_sync/`

RealAnalyst 中路径已归并到 `skills/metadata/adapters/` 和 `metadata/sync/`，但报告章节和生成逻辑应保持同一范式。

## 推荐工作流

### 1. 先确认 metadata 当前状态

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py inventory
python3 {baseDir}/skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
```

如果 `validate` 失败，报告必须把失败项写成“待修复问题”，不要把未通过校验的定义写成确定口径。

### 2. 优先生成或读取 sync report

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/generate_sync_report.py --key <source_key>
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --all-yaml
```

DuckDB 报告入口选择：

- `--dataset-id <dataset_id>`：首选。基于已维护的 metadata YAML 生成单个注册报告。
- `--all-yaml`：基于 metadata YAML 为全部 DuckDB dataset 生成注册报告。
- `--source <dataset_id>`：`--dataset-id` 的兼容别名。
- `--key <source_key>` / `--all`：只用于 runtime registry 同步报告，不作为业务口径真源。

如果已有 sync report，优先读取最新报告；不要为了写说明重复同步外部系统。

### 3. 按标准模板补充说明

需要人工补写或审阅时，先读取：

```text
{baseDir}/skills/metadata-report/references/report-template.md
```

该模板是脚本输出结构的人工写作版；脚本能生成的内容以脚本为准，模板用于补齐解释、证据和待确认项。

## 报告结构

Tableau 报告至少包含：

1. `## 1. 同步任务概览`
2. `## 2. 数据源注册信息`
3. `## 3. 本次写入摘要`
4. `## 4. 建议补充的业务描述`
5. `## 5. 逻辑字段明细`
6. `## 6. 筛选器明细`
7. `## 7. 参数明细`
8. `## 8. 指标与维度映射结果`
9. `## 9. 导出验证与结构差异`
10. `## 10. 本条数据源的结论`

DuckDB 报告至少包含：

1. `## 1. 同步任务概览`
2. `## 2. 数据源注册信息`
3. `## 3. 本次写入摘要`
4. `## 4. 语义层明细`
5. `## 5. 字段明细`
6. `## 6. 指标明细`
7. `## 7. 筛选器明细`
8. `## 8. 映射与 Review 问题`
9. `## 9. 校验结果`
10. `## 10. 本条数据源的结论`

字段表推荐列，详见 `references/report-template.md`。核心列如下：

| 展示名 | 源字段 | 类型 | 角色 | 业务定义 | 定义来源 | 示例值 | 证据 | Review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

指标表推荐列：

| 指标 | 公式/表达式 | 聚合方式 | 单位 | 适用粒度 | 证据 | Review |
| --- | --- | --- | --- | --- | --- | --- |

筛选器/参数表推荐列：

| 名称 | 类型 | 用法 | 可选值/示例 | 是否必填 | 来源 |
| --- | --- | --- | --- | --- | --- |

DuckDB 报告中的示例值应从 DuckDB 当前对象只读采样得到；它们只用于帮助业务识别筛选写法和字段值域，不代表完整枚举清单，也不替代 YAML 中的业务定义。

## 写作规则

1. 先列“同步/注册了什么”，再解释“这些元数据能支持什么分析”。
2. 对每个字段、指标、筛选器，尽量写清来源文件或 sync report 章节。
3. `needs_review=true`、`review_required=true`、低置信度或无证据项必须显式标记。
4. 不把 Tableau 参数写成普通筛选器；Tableau `filters` 和 `parameters` 必须分开说明。
5. 不把 DuckDB 表结构直接当业务口径；表结构只说明字段存在。
6. 不写泛泛总结；报告必须列出字段、指标、筛选器、参数、适用/不适用场景。
7. 报告是给业务和分析人员复核的，少写系统实现细节，多写口径、边界和使用方式。
8. Tableau 报告必须分清 `--vf` 筛选器和 `--vp` 参数；DuckDB 报告必须分清 `sql_where` 筛选器和字段/指标。
9. DuckDB YAML 模式下，`registry=not_written` 是正常状态；报告必须说明“未反写 registry，不把 registry.db 当业务口径真源”。
10. 不展示旧 YAML 的 `schema_note`，也不要生成“Schema 说明”列；字段存在性、DuckDB 类型、Tableau 字段名只能作为结构化类型或证据来源，不作为业务定义。

## 质量门禁

完成前检查：

- 已说明 metadata 来源：dataset YAML、mapping、dictionary、source 或 sync report。
- 字段、指标、筛选器、参数没有混写。
- 所有不确定项都进入 `待确认问题`。
- 没有把未校验 YAML、connector 字段名或 runtime registry 写成确定业务定义。
- 输出路径符合报告类型，且 Markdown 能独立阅读。

## 常见误区

| 误区 | 正确做法 |
| --- | --- |
| 只写“已同步成功” | 列清同步对象、字段、指标、筛选器、参数和 review 问题 |
| 用字段名猜业务定义 | 回到 dictionaries / mappings / sources 找证据；找不到就标记待确认 |
| 把 metadata report 写成分析报告 | 只说明元数据能力和边界，不输出业务经营结论 |
| 把 `schema_note` 当业务说明展示 | 报告只展示 `business_definition.text`、定义来源、证据和 review 状态 |
| 忽略筛选器枚举值 | 可列举值、默认值、参数用法必须单独写 |
| 遇到 validate 失败仍继续写确定口径 | 报告降级为"元数据待修复报告"，失败项进入待确认问题 |

## Completion Summary

元数据报告完成后，向用户汇报：

1. 生成了哪种类型的报告（同步报告 / 注册说明 / review gap 报告）。
2. 报告输出路径。
3. 存在多少待确认项（review gap / needs_review / 校验失败项）。
4. 下一步建议：修复待确认项后进入 `/skill RA:metadata` 继续维护元数据，或进入 `/skill RA:analysis-plan` 开始分析。
