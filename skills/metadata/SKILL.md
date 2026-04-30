---
name: "RA:metadata"
description: Use when initializing, registering, refreshing, validating, searching, or packaging LLM-maintained dataset metadata for RealAnalyst; trigger for 数据集注册, 元数据初始化, 指标/字段/术语查询, 业务口径维护, metadata context, Tableau/DuckDB source onboarding, or analysis planning context.
---

# Metadata Skill

RealAnalyst 的统一元数据入口。它负责把“数据源发现、业务语义维护、低 token 检索、分析上下文构造”收敛成一条链路；细节契约放在 `references/`，本文件只保留触发条件、执行顺序和硬门禁。

核心原则：**sources 是证据层；dictionaries 是公共语义层；mappings 是字段映射层；datasets 只放真实数据源；index/context 是生成层；`runtime/registry.db` 是运行层；OSI 是交换层。**

## When to Use

使用本 skill：

- 用户要注册数据集、初始化元数据、维护字段/指标/术语。
- 用户给出 `metadata/sources/refine/{refine_id}/` 参考材料，需要据此修正正式 YAML。
- 分析前需要查指标、字段、业务定义、同义词或适用场景。
- 用户提到 Tableau / DuckDB source onboarding，且目标是进入统一元数据体系。
- 需要为 `RA:analysis-plan` 生成小型 metadata context pack。
- 需要检查 LLM 维护的 YAML 是否满足字段、指标、证据、置信度和 review 契约。

不要使用本 skill：

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

然后只修改相关 dictionaries / mappings / datasets YAML。新增或修正的 `business_definition.source_evidence[].source` 必须引用 `metadata/sources/refine/{refine_id}/...`，不引用 runtime 临时路径。

4. 校验、生成索引、同步运行层：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
```

校验失败时停止，先修 YAML。`sync-registry` 是唯一允许从已校验 YAML 写入 `runtime/registry.db` 的路径。

5. 需求理解阶段先低 token 检索，不直接扫完整 YAML：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type metric --query 收入
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type field --query 航班日期
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query 转化率
```

6. 浏览数据集目录（选源阶段使用，token 开销低）：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog --domain <domain>
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog --group-by domain
```

catalog 输出每个 dataset 的轻量摘要（id / display_name / domain / grain / top 3 metrics / suitable_for / field_count / metric_count / review_required），适合在需求理解阶段快速了解可用数据集全貌。

7. 构造分析上下文：

```bash
# 单数据集
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id> --metric <metric> --field <field>

# 多数据集（输出带 mode=multi 的合并 context）
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
```

context pack 是 `RA:analysis-plan` 的正式语义输入。若输出中出现 `needs_review=true` 或 `review_required=true`，必须在计划、报告和验证中标记为推断口径。

多数据集 context 输出包含 `shared_dictionary_refs`（共享字典引用）和 `shared_glossary`（去重后的共享术语）。

8. 比对运行时配置与元数据 YAML 的指标/维度/术语差异：

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
| Tableau/DuckDB 字段需要刷新 | 读取 `references/connector-adapters.md`，通过 adapter scripts 获取素材 |
| 需要跨系统标准交换 | 使用 `metadata export-osi`；不要新建独立 `osi-export` skill |
| 用户给了配置抽取文档 | 先保存到 `metadata/sources/`，再拆成 dictionaries/mappings/datasets |
| 用户给了 refine 参考材料 | 读取 `metadata/sources/refine/{refine_id}/evidence_manifest.json` 和 `metadata_update_reference.md`，再维护正式 YAML |
| 怀疑运行时与元数据指标/维度不一致 | 运行 `metadata reconcile`，根据输出修补 YAML 或 runtime 配置 |

## Quality Gates

继续分析前必须满足：

- `metadata validate` 返回 `success=true`。
- `metadata index` 成功生成 `metadata/index/*.jsonl`，包括 mappings 索引。
- `metadata status --dataset-id ...` 显示 `metadata_yaml=true`、`metadata_index=true`、`runtime_registry=true`；需要取数时还要 `export_ready=true`。
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
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
python3 {baseDir}/skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog
python3 {baseDir}/skills/metadata/scripts/metadata.py catalog --domain <domain>
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <query>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
python3 {baseDir}/skills/metadata/scripts/metadata.py reconcile
python3 {baseDir}/skills/metadata/scripts/metadata.py inventory
python3 {baseDir}/skills/metadata/scripts/metadata.py export-osi --model-name <model_name>
```

## Completion Summary

每类 metadata 任务完成后，向用户汇报：

- **validate 完成**：校验结果（成功/失败项数）。下一步：`metadata index` 生成索引。
- **index 完成**：生成了多少条 JSONL 记录，search.db 是否创建。下一步：`metadata search` 或 `metadata catalog` 浏览数据集。
- **catalog 完成**：列出了多少个数据集。下一步：选定候选数据集后运行 `metadata context`。
- **search 完成**：命中了多少条记录，使用了哪个后端（FTS5 / JSONL）。下一步：用命中的 dataset_id 生成 `metadata context`。
- **context 完成**：为哪些数据集生成了 context pack，是否有 `review_required` 或 `missing_fields`。下一步：进入 `/skill RA:analysis-plan` 或 `/skill RA:analysis-run`。
- **reconcile 完成**：各类别匹配数、不一致数。下一步：修补 YAML 或 runtime 配置中的差异项。
- **sync-registry 完成**：同步了哪些 dataset 到 registry。下一步：`metadata status` 确认状态。
