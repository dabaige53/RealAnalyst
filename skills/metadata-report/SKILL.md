---
name: "RA:metadata-report"
description: |
  Use when generating Markdown reports that explain RealAnalyst metadata, sync results, dataset registration details, field/metric/filter semantics,
  metadata gaps, or metadata inventory. Triggers: 元数据报告, 同步结果说明, 字段口径说明, 数据集注册报告, 元数据清单.
---

# Metadata Report Skill

用于把 RealAnalyst 的元数据、连接器同步结果、数据源注册信息和待补齐项写成可复核的 Markdown 报告。它只负责“阐述元数据”，不负责注册数据集、取数分析或改写业务结论。

本 skill 是 dataset-first 元数据 Markdown 报告的唯一出口。报告统一通过 `skills/metadata-report/scripts/generate_report.py` 生成；主入口不要求用户提供 connector。正文按“元数据事实摘要 -> 数据集信息 -> 字段信息 -> 指标信息 -> 筛选、参数与取值信息 -> 映射与来源追溯 -> 未维护项 -> 运行与注册状态 -> 报告生成信息”组织。

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
字段和指标必须按通用结构处理：role、business_definition、expression、aggregation、mapping、dictionary、evidence 和 validate 状态。禁止为了某个具体业务字段名、指标名或固定中文列名写特例补丁。

优先级如下：

1. `metadata/datasets/*.yaml`：数据集说明、字段、指标、时间字段、粒度、适用边界。
2. `metadata/mappings/*.yaml`：源字段到标准语义的映射和补齐状态。
3. `metadata/dictionaries/*.yaml`：公共指标、维度、术语的业务定义。
4. `metadata/sources/`：原始证据、用户文档、connector discovery 归档。
5. `runtime/registry.db`：只说明运行时是否可取数、是否已维护筛选值或范围，不作为业务定义来源。
6. `metadata/index/search.db` / JSONL index：作为检索层事实状态，不替代 dataset YAML。

报告事实必须通过 `skills/metadata/lib/metadata_facts.py` / `metadata.py read` 这类统一读取能力进入报告层。report 脚本只做展示编排，不另起一套 broad YAML / registry parser。

## 标准脚本入口

优先使用统一报告生成脚本，不手写从零拼报告。

| 报告类型 | 脚本 | 默认输出目录 |
| --- | --- | --- |
| 单数据集元数据报告 | `skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id>` | `metadata/reports/<dataset_id>_metadata_report.md` |
| 全部数据集元数据报告 | `skills/metadata-report/scripts/generate_report.py --all` | `metadata/reports/` |
| 指定输出目录 | `skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id> --output-dir <dir>` | `<dir>/<dataset_id>_metadata_report.md` |
| connector 兼容报告 | `skills/metadata-report/scripts/generate_report.py --connector <connector> ...` | legacy compatibility only |

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
python3 {baseDir}/skills/metadata/scripts/metadata.py read --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata-report/scripts/generate_report.py --all
```

不要为了生成报告运行 `RA:data-profile`、读取 `jobs/*/profile/*`、现场查询 DuckDB 或现场采样。取值、范围、筛选器和参数只读取长期 metadata / runtime registry 已维护事实；没有就写“未维护”。

### 3. 按标准模板补充说明

需要人工补写或审阅时，先读取：

```text
{baseDir}/skills/metadata-report/references/report-template.md
```

该模板是脚本输出结构的目标写作版；脚本若仍输出旧结构，以模板作为后续改造目标，人工补写时优先遵循模板。

## 报告结构

dataset-first 报告章节顺序固定：

1. `## 1. 元数据事实摘要`
2. `## 2. 数据集信息`
3. `## 3. 字段信息`
4. `## 4. 指标信息`
5. `## 5. 筛选、参数与取值信息`
6. `## 6. 映射与来源追溯`
7. `## 7. 未维护项`
8. `## 8. 运行与注册状态`
9. `## 9. 报告生成信息`

没有真实内容的 section 不输出；缺失事实统一进入“未维护项”。表头、章节和状态标签用中文；metadata 原始值不翻译、不改写。

## 写作规则

1. 先给“元数据事实摘要”，再列数据集、字段、指标和筛选取值事实。
2. 正文不要堆内部实现说明；系统字段只作为追溯信息，不作为阅读主线。
3. 字段、指标、筛选器、参数不能删；没有维护的单元格写“未维护”。
4. `needs_review=true`、`review_required=true` 或无证据项必须显式进入“未维护项”。
5. 不把 Tableau 参数写成普通筛选器；Tableau `filters` 和 `parameters` 必须分开说明。
6. 不把 DuckDB 表结构直接当业务口径；表结构只说明字段存在。
7. 不写泛泛总结；报告必须列出真实存在的字段、指标、筛选器、参数、适用/不适用场景；没有内容的 section 直接删除。
8. 报告是给分析师复核的，少写系统实现细节，多写口径、边界和调用方式。
9. Tableau 报告必须分清 `--vf` 筛选器和 `--vp` 参数；DuckDB 报告必须分清 `sql_where` 筛选器和字段/指标。
10. registry 不存在或未注册时报告继续生成，状态显示“未注册”。
11. 不展示旧 YAML 的 `schema_note`，也不要生成“Schema 说明”列；字段存在性、DuckDB 类型、Tableau 字段名只能作为结构化类型或证据来源，不作为业务定义。
12. 不根据 role/status 自动生成字段或指标的“常见用途”“使用建议”；元数据没有显式维护时，删除这些列或显示“未维护”。
13. 字段、指标和映射明细必须显式展示“语义引用状态”，让用户区分标准定义引用、映射覆盖引用、本地口径和待补齐项。
14. 不生成 `*_metadata_context.json` 伴生文件；agent 需要结构化读取时使用 `RA:metadata` 的 `read/search/status`。

## 质量门禁

完成前检查：

- 已说明元数据来源：dataset YAML、mapping、dictionary、metadata index 或 runtime registry。
- 字段、指标、筛选器、参数没有混写。
- 所有不确定项都进入“未维护项”。
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
- 报告内容必须来自真实 metadata、metadata search/read/status、runtime registry、mapping 或 dictionary evidence。
```
