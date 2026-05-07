---
name: "RA:metadata"
description: Use when initializing, registering, refreshing, validating, or packaging LLM-maintained dataset metadata for RealAnalyst; trigger for 数据集注册, 元数据初始化, 业务口径维护, metadata context, Tableau/DuckDB source onboarding, or analysis planning context. For search/catalog use RA:metadata-search.
---

# Metadata Skill

RealAnalyst 的统一元数据入口。它负责把“数据源发现、业务语义维护、低 token 检索、分析上下文构造”收敛成一条链路；细节契约放在 `references/`，本文件只保留触发条件、执行顺序和硬门禁。

核心原则：**sources 是证据层；dictionaries 是公共语义层；mappings 是字段映射层；datasets 只放真实数据源；index/context 是生成层；`runtime/registry.db` 是运行层；OSI 是交换层。**

本 skill 是数据未注册或口径未维护时的主入口。它可以完成最小可分析注册，让一次正式分析安全启动；它不会默认自动生成长期 `RA:metadata-report`，只在完成时提示用户可主动调用。

## When to Use

使用本 skill：

- 用户要注册数据集、初始化元数据、维护字段/指标/术语 YAML。
- 用户给出 `metadata/sources/refine/{refine_id}/` 参考材料，需要据此修正正式 YAML。
- 用户提到 Tableau / DuckDB source onboarding，且目标是进入统一元数据体系。
- 需要为 `RA:analysis-plan` 生成 metadata context pack（`metadata context --dataset-id`）。
- 需要检查 LLM 维护的 YAML 是否满足字段、指标、证据、置信度和 review 契约。

不要使用本 skill：

- **搜索指标、字段、术语、dataset 或 mapping 定义**：使用 `RA:metadata-search`。
- **浏览数据集目录（catalog）**：使用 `RA:metadata-search`。
- 已经进入正式数据导出阶段：Tableau / DuckDB 取数使用 `RA:data-export`。
- 用户只要求写报告、做 data profile 或 report verify。
- 用户只要求整理分析 job 反馈、探查真实数据并生成修正参考材料：使用 `RA:metadata-refine`。
- 用户明确要求操作 Tableau Server 或 DuckDB 运行态脚本本身；此时说明它是 connector adapter，不把它当业务口径真源。

## Reference First

执行前按场景读取最小 reference：

| 场景 | 读取 |
| --- | --- |
| 维护分层、review 规则、运行层边界 | `references/maintenance-contract.md` |
| 判断 YAML 应落到 sources / dictionaries / mappings / datasets 哪一层 | `references/yaml-structure-contract.md` |
| Tableau / DuckDB 字段刷新、adapter handoff、connector 禁止事项 | `references/connector-adapters.md` |

不要把这些细节复制回 `SKILL.md`。入口保持轻，契约放 reference。

## Operating Model

metadata skill 只暴露一个用户入口，但内部有清楚分层：

| 层级 | 本文件内记住什么 | 细节在哪里 |
| --- | --- | --- |
| sources | 原始证据先归档，不直接当分析上下文 | `yaml-structure-contract.md` |
| dictionaries | 公共指标、维度、术语的语义真源 | `maintenance-contract.md` |
| mappings | source 字段到标准语义的映射和口径覆盖 | `yaml-structure-contract.md` |
| datasets | 一个真实可分析对象一份 YAML | `yaml-structure-contract.md` |
| index / context | 生成层；需求理解先 search，再 context | `maintenance-contract.md` |
| connector adapter | 只提供 Tableau / DuckDB 初始化素材 | `connector-adapters.md` |
| registry.db | 运行层；只允许 `sync-registry` 受控写入 | `maintenance-contract.md` |
| OSI | 交换层；不进入本地分析主路径 | `maintenance-contract.md` |

Tableau/DuckDB 字段和筛选器只能作为素材。业务定义、确定口径和 review 状态必须回到 metadata YAML。

## Core Workflow

1. 初始化或补齐元数据工作区：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py init
```

最小可分析注册必须满足：

- 有明确 dataset id 和数据源类型。
- 有可用数据获取方式：Tableau / DuckDB / CSV 等。
- 核心字段已识别：时间、主体、维度、指标候选。
- 指标/字段定义有状态：已确认、文档来源、行业草稿、LLM 推断、待确认。
- 本次分析所需字段能被找到。
- 输出本次口径快照/注册摘要，方便用户看过。
- registry / index / context 至少能支持 `RA:analysis-run` 找到数据和口径。

最小注册不是完整治理。注册完成后提示用户如需长期口径说明，主动调用 `RA:metadata-report`。

2. 如需外部 source 素材，先生成 adapter handoff，不直接写运行层：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py init-source --backend tableau --source-id <source_id> --dry-run
python3 {baseDir}/skills/metadata/scripts/metadata.py init-source --backend duckdb --source-id <source_id> --dry-run
```

3. 按 `references/yaml-structure-contract.md` 维护 YAML：

- 原始材料归档到 `metadata/sources/`。
- 公共指标、维度、术语放到 `metadata/dictionaries/`。
- source 字段到标准语义的映射放到 `metadata/mappings/`。
- 真实可分析对象放到 `metadata/datasets/`，并引用 dictionaries / mappings。

若输入来自 `RA:metadata-refine`，先读取：

```text
metadata/sources/refine/{refine_id}/evidence_manifest.json
metadata/sources/refine/{refine_id}/metadata_update_reference.md
```

然后只修改相关 dictionaries / mappings / datasets YAML。dataset 字段/指标不得复制 evidence；需要追溯时写 `business_definition.ref`，指向 dictionary、mapping 或 `metadata/audit` 关联记录。

4. 每次维护 YAML 后必须记录变更日志并生成报告：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py record-change --summary "<本次修改了什么>" --change-type maintenance --path metadata/datasets/<dataset>.yaml --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py change-report
```

默认输出：

```text
metadata/audit/metadata_changes.jsonl
metadata/audit/metadata_relations.jsonl
metadata/audit/metadata_change_report.md
```

如果字段或指标通过 `business_definition.ref` 指向 dictionary、mapping 或 refine evidence，记录关联而不是复制 evidence：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py record-relation --ref <definition_ref> --dataset-id <dataset_id> --section fields --name <field_name> --source-type dictionary --target metadata/dictionaries/<dict>.yaml --evidence metadata/sources/refine/<refine_id>/evidence_manifest.json
```

`metadata/audit/metadata_relations.jsonl` 只服务追溯和维护，不进入分析 context，也不作为业务定义真源。

如果本次修改来自 `RA:metadata-refine`，修改前必须先保存旧 YAML 副本；记录时追加 `--refine-id <refine_id>`、`--before <旧YAML副本>` 和 `--evidence metadata/sources/refine/<refine_id>/evidence_manifest.json`。此时会生成对比报告：

```text
metadata/audit/refine-diffs/<refine_id>-<timestamp>.md
```

5. 校验、生成索引、同步运行层：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py validate --completeness
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
```

普通 `validate` 同时检查结构和 dataset 责任边界；`validate --completeness` 会额外检查 metric-like 字段和 mapping metric 是否完整。校验失败时停止，先修 YAML。`sync-registry` 是唯一允许从已校验 YAML 写入 `runtime/registry.db` 的路径。

Dataset YAML 只放语义元数据，不放运行时画像或副本数据：

- 不写 `sample_profile`、`sample_values`、`top_values`、`enum_values`。
- 不在字段或指标内嵌 `source_mapping`、`definition_source` 或字段级裸 `source_evidence`。
- 字段/指标定义不写 `business_definition.source_evidence`、`quote` 或文档路径；使用 `business_definition.ref` 指向 dictionary/mapping/audit 证据链。
- `description` 和 `business_definition.text` 不得完全重复。
- source mapping 维护到 `metadata/mappings/*.yaml`；样本画像和枚举候选维护到 `metadata/sources/refine/` 或 `runtime/registry.db`。
- `business_definition.source_type=pending` 不得注册为正式 `metrics`；先留在 fields、refine 建议或补齐清单中。
- 单个 dataset YAML 超过 1000 行会产生膨胀预警，超过 1500 行会被视为责任边界失败，需要拆出 profile、enum、registry snapshot 或重复 evidence。

6. 需求理解阶段先低 token 检索，不直接扫完整 YAML：

> 推荐使用独立 skill `RA:metadata-search` 作为检索入口（更清晰的职责边界）；
> 也可直接使用以下命令：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type metric --query 收入
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type field --query 航班日期
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query 转化率
```

7. 浏览数据集目录（选源阶段使用，token 开销低）：

> 推荐使用独立 skill `RA:metadata-search` 的 catalog 入口；也可直接使用以下命令：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog --domain <domain>
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog --group-by domain
```

catalog 输出每个 dataset 的轻量摘要（id / display_name / domain / grain / top 3 metrics / suitable_for / field_count / metric_count / review_required），适合在需求理解阶段快速了解可用数据集全貌。

8. 构造分析上下文：

```bash
# 单数据集
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id> --metric <metric> --field <field>

# 多数据集（输出带 mode=multi 的合并 context）
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
```

context pack 是 `RA:analysis-plan` 的正式语义输入。若输出中出现 `needs_review=true` 或 `review_required=true`，必须在计划、报告和验证中标记为推断口径。

多数据集 context 输出包含 `shared_dictionary_refs`（共享字典引用）和 `shared_glossary`（去重后的共享术语）。

8. 基于 profile/refine 证据生成 metadata 完整性审查报告：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py profile-review --dataset-id <dataset_id> --refine-id <refine_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py profile-review --dataset-id <dataset_id> --profile-json jobs/<SESSION_ID>/profile/profile.json
```

`profile-review` 只输出 Markdown + JSON 建议，不自动改 YAML。它会把缺口分成“应补指标 / 待人工确认 / 不建议注册为指标”。

9. 比对运行时配置与元数据 YAML 的指标/维度/术语差异：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py reconcile
```

reconcile 输出每个类别（metrics / dimensions / glossary）的匹配数、仅运行时存在项、仅元数据存在项、以及定义不一致项，用于发现两套系统的语义漂移。

## Decision Rules

| 情况 | 动作 |
| --- | --- |
| 用户只给指标/术语，没有 dataset | 先 `metadata catalog` 浏览全貌，再 `metadata search` 定位候选，最后按候选 dataset 生成 context |
| 用户给了 dataset 和指标 | 先 `metadata context --dataset-id ... --metric ...`，再用 context 中的 `dataset.runtime_source_id` 查 runtime registry |
| index 缺失 | 运行 `metadata validate`，通过后运行 `metadata index` |
| registry 缺失 | 运行 `metadata sync-registry --dataset-id ... --dry-run`，确认后正式同步 |
| YAML 缺字段/指标定义 | 先补 YAML，设置证据、置信度和 review 标记 |
| YAML 已修改 | 运行 `metadata record-change` 写入审计日志，再运行 `metadata validate` / `metadata index` |
| Tableau/DuckDB 字段需要刷新 | 读取 `references/connector-adapters.md`，通过 adapter scripts 获取素材 |
| 需要跨系统标准交换 | 使用 `metadata export-osi`；不要新建独立 `osi-export` skill |
| 用户给了配置抽取文档 | 先保存到 `metadata/sources/`，再拆成 dictionaries/mappings/datasets |
| 用户给了 refine 参考材料 | 读取 `metadata/sources/refine/{refine_id}/evidence_manifest.json`、`refine_followup.md` 和 `metadata_update_reference.md`，再维护正式 YAML |
| 需要确认真实样本是否已转成指标/枚举/evidence | 运行 `metadata profile-review --dataset-id ... --refine-id ...`，按报告补 YAML |
| 基于 refine 修改 YAML | 修改前保存旧 YAML 副本；修改后运行 `metadata record-change --refine-id ... --before ...`，生成 diff 报告 |
| 怀疑运行时与元数据指标/维度不一致 | 运行 `metadata reconcile`，根据输出修补 YAML 或 runtime 配置 |

## Quality Gates

继续分析前必须满足：

- `metadata validate` 返回 `success=true`。
- metadata 来自真实样本/refine 时，`metadata profile-review` 已生成报告；正式分析前建议运行 `metadata validate --completeness`。
- `metadata index` 成功生成 `metadata/index/*.jsonl`，包括 mappings 索引。
- `metadata status --dataset-id ...` 显示 `metadata_yaml=true`、`metadata_index=true`、`runtime_registry=true`；需要取数时还要 `export_ready=true`。
- 修改 YAML 后必须存在本轮 `metadata/audit/metadata_changes.jsonl` 记录，并刷新 `metadata/audit/metadata_change_report.md`。
- 基于 refine 修改 YAML 后必须生成 `metadata/audit/refine-diffs/*.md`，说明前后差异。
- 需求理解只读取 search/context 结果，不扫完整 YAML。
- `needs_review=true` 不得作为确定口径通过验证。
- 不手工覆盖 `registry.db`；只能用 `metadata sync-registry` 从已校验 YAML 受控 upsert。
- connector adapter 产出的字段信息必须回填到 YAML 后再被分析流程使用。

## Common Mistakes

| 错误 | 修正 |
| --- | --- |
| 直接读完整 YAML 来理解需求 | 先 `metadata search`，再 `metadata context` |
| 把公共术语/指标总表放进 `datasets/` | 拆到 `dictionaries/`；`datasets/` 只收真实数据源 |
| 把 source 字段映射塞进公共字典 | 拆到 `mappings/`；字典只放标准语义 |
| 只引用用户 Downloads 里的原始文件 | 复制到 `metadata/sources/` 后再作为证据引用 |
| 把 Tableau/DuckDB 字段名当业务定义 | 字段名只是素材，业务定义写回 YAML |
| 引用 `runtime/metadata-refine/` 作为证据 | 先用 `RA:metadata-refine` 归档到 `metadata/sources/refine/`，YAML 只引用归档路径 |
| 改完 YAML 只跑 validate/index | 还必须跑 `metadata record-change`，留下本次修改原因、文件和证据 |
| 基于 refine 改 YAML 但没有对比报告 | 先保存旧 YAML 副本，再用 `metadata record-change --refine-id ... --before ...` 自动生成 diff 报告 |
| validate/index 成功就说“可取数” | 先跑 `metadata status`；runtime registry 和 export-ready 要单独验收 |
| 创建新的 connector-specific skill | 停止；把能力接进 metadata adapter |

## Failure Handling

- search 返回 index missing：运行 `metadata validate` 和 `metadata index`。
- context 返回 missing fields/metrics：回到 search 确认拼写，再维护 YAML。
- validate 返回低置信度错误：补证据或设置 `needs_review=true`。
- adapter 脚本失败：修 connector 脚本根因，不手工绕过；失败细节写入初始化报告或分析计划限制项。
- source 冲突：向用户列出候选 dataset、关键字段和适用场景，请用户确认。

## CLI Quick Reference

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py list-commands
python3 {baseDir}/skills/metadata/scripts/metadata.py init
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py validate --completeness
python3 {baseDir}/skills/metadata/scripts/metadata.py validate --strict
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py record-change --summary <summary> --path <metadata_yaml>
python3 {baseDir}/skills/metadata/scripts/metadata.py record-change --summary <summary> --path <metadata_yaml> --before <old_yaml_copy> --refine-id <refine_id> --evidence metadata/sources/refine/<refine_id>/evidence_manifest.json
python3 {baseDir}/skills/metadata/scripts/metadata.py change-report
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog --domain <domain>
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <query>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
python3 {baseDir}/skills/metadata/scripts/metadata.py reconcile
python3 {baseDir}/skills/metadata/scripts/metadata.py profile-review --dataset-id <dataset_id> --refine-id <refine_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py profile-review --dataset-id <dataset_id> --profile-json jobs/<SESSION_ID>/profile/profile.json
python3 {baseDir}/skills/metadata/scripts/metadata.py inventory
python3 {baseDir}/skills/metadata/scripts/metadata.py export-osi --model-name <model_name>
```

## Completion Summary

每类 metadata 任务完成后，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已完成：<init / validate / record-change / index / context / sync-registry / status / reconcile / profile-review>
- 产物/检查：<metadata YAML、audit report、index、context pack、registry sync、status、gap report>
- 本次口径快照：<dataset id、source 类型、核心字段、核心指标、定义状态、review 标记>

下一步建议：
- 最推荐下一步：/skill RA:analysis-run ...（metadata_index、runtime_registry、export_ready 已满足）
- 可选下一步：/skill RA:metadata-report ...（需要生成长期数据集口径说明时）
- 可选下一步：/skill RA:metadata ...（仍需补 YAML、definition、mapping、review gap 时继续维护）

边界提醒：
- 本 skill 没有默认自动生成长期 metadata report；如需说明书请主动调用 /skill RA:metadata-report。
- 本 skill 没有执行正式分析、取数、画像或报告写作；正式分析进入 /skill RA:analysis-run。
- `sync-registry` 只把已校验 metadata 写入 runtime registry，不把 registry 当业务定义真源。
```
