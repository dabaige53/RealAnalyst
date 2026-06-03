# Skill-Driven Usage Guardrails

## Goal

优化 RealAnalyst 的 skills 驱动工作流，让用户通过 skill 正常使用项目时，agent 能先进入正确的项目环境初始化流程，再按明确的 skill 职责执行分析、取数、metadata 维护或 refine 交接，并且由 `RA:metadata` 产出结构更标准、内容更干净的 dataset YAML。整改要避免把用户的展示/取数需求误判成 metadata YAML 修改，也避免 agent 自己猜环境、绕过受控入口写 runtime 或 generated files。

## What I Already Know

* 用户使用的是 RealAnalyst skills，而不是直接读 README 手工操作；整改主对象应是 skill 入口、skill 文档、脚本化环境初始化和 skill 之间的交接合同。
* 最近在下游项目 `testkpi` 的一次会话中，用户只想让“取数结果字段名转中文”，这本应属于 `RA:data-export` 的 export/display layer；agent 却误进入 metadata 维护思路，把 `metadata/datasets/*.yaml` 的 `fields[].name` 改成中文展示名。
* 同一会话暴露了环境误判：项目缺 Python `duckdb` 依赖、文档引用 `./scripts/py` 但下游项目没有该入口、agent 自己探测环境后绕到 DuckDB CLI、并直接写 `runtime/registry.db`。
* 这说明问题不是“用户没有读文档”，而是 skills 没有在执行前明确指定项目环境、运行入口、依赖检查、允许写入范围和跨 skill 交接方式。
* 当前相关 skill：
  * `RA:analysis-run`：正式分析入口，应该初始化/复用 job，只记录 metadata 问题，不直接修 YAML。
  * `RA:data-export`：正式取数入口，应该解决 CSV/header/display 输出问题，不写正式 metadata YAML。
  * `RA:metadata`：只有用户明确要注册/维护 metadata 时，才允许写 dataset/mapping/dictionary 和 sync registry。
  * `RA:metadata-refine`：把分析中发现的字段/口径/证据问题整理成参考材料，供之后 `RA:metadata` 维护。
  * `RA:getting-started`：应成为下游项目环境初始化和路径选择的第一站。
* 现有 YAML 结构契约已经明确：`metadata/datasets/*.yaml` 是轻量语义入口，不是 profile store、enum store、mapping file、registry snapshot 或 report archive；本次整改需要把这个契约从“文档约定”升级成 `RA:metadata` 的输出标准和校验标准。

## Current Problem

当前问题集中在两类误判：

### 1. Skill 路由误判

用户说“字段名称转中文”时，agent 没有区分：

* 导出结果的列名/header/display name：应由 `RA:data-export` 处理。
* metadata 字段 identity / `fields[].name`：只有 `RA:metadata` 维护任务才能改。

因此一个展示层需求被误执行成 metadata YAML 维护。

### 2. 项目环境误判

agent 遇到环境不匹配时靠自己发现和绕路：

* 找不到 `./scripts/py` 后改用 `python3`。
* Python 缺 `duckdb` 后改用 DuckDB CLI。
* `sync-registry --dry-run` 暴露风险后，直接用 `sqlite3` 写 `runtime/registry.db`。

这不是用户合理使用失败，而是 skill 没有先提供明确的项目环境初始化合同。agent 不应该自由猜测运行环境；应先由 `RA:getting-started` 或 `RA:doctor` 明确告诉它当前项目应该使用哪个 Python、哪个脚本入口、哪些依赖缺失、哪些写入被允许。

### 3. YAML 结构和内容质量不稳定

之前的 `duckdb.ho.view_dwd_zy_flight_results.yaml` 曾出现过明显膨胀和职责混杂；本轮虽然已经收敛到更小文件，但仍暴露出字段 identity、display name、physical/source field 容易混写的问题。`RA:metadata` 不应只“生成合法 YAML”，还应生成结构标准、内容干净、层次清楚的 YAML：

* dataset 只保留数据集身份、业务边界、核心字段、正式指标和引用关系。
* profile、枚举候选、sample/top values、DuckDB 类型、nullable、registry snapshot、report 内容不进入 dataset。
* `fields[].name` 是稳定语义 ID，不是中文展示名；中文展示名放 `display_name`。
* `physical_name/source_field` 是真实源字段，不应被用来替代语义 ID。
* pending candidate 不进入正式 `metrics`。

## Requirements

### 1. Skill Router Contract

为核心 skill 增加明确路由规则：

* `RA:data-export`
  * 处理取数结果、CSV 表头、字段展示名、导出格式、output contract。
  * 明确禁止修改 `metadata/datasets/*.yaml` 的 `fields[].name`。
  * 如果发现字段定义不清，只写 metadata feedback 或提示转 `RA:metadata-refine`。
* `RA:analysis-run`
  * 分析过程中发现 metadata 问题时，只记录到 job 的 `metadata_feedback.jsonl`。
  * 不在分析流程中直接修改正式 metadata YAML、runtime registry 或 index。
  * 需要补注册/修口径时，明确交接给 `RA:metadata-refine` 或 `RA:metadata`。
* `RA:metadata`
  * 只有用户明确表达“注册数据集、维护字段定义、修改 metadata YAML、同步 registry、修 metadata 口径”时才进入。
  * 要求执行前确认本轮目标是 metadata 维护，而不是分析展示或导出格式。
* `RA:metadata-refine`
  * 接收分析反馈和 profile 证据，生成修正参考包。
  * 不直接替代 `RA:metadata` 写正式 YAML。
* `RA:getting-started`
  * 先判断用户当前意图属于分析、取数、metadata 注册/维护、refine、环境初始化中的哪一类。
  * 输出推荐 skill 路径，而不是让 agent 自由选择。

### 2. Project Environment Initialization Contract

新增或强化一个由 skill 驱动的项目环境初始化流程，目标是“先指定环境，再执行任务”：

* 检查并输出项目可用的运行入口：
  * Python interpreter / virtualenv path。
  * 是否存在 `./scripts/py`；不存在时推荐项目实际入口，而不是让 agent 临场猜。
  * RealAnalyst source layout 与 project-local `.agents/skills` layout。
* 检查依赖：
  * Python `duckdb` 是否可 import。
  * DuckDB CLI 是否可用只能作为诊断信息，不应默认替代受控 Python export path。
* 检查 registry 和数据路径：
  * `runtime/registry.db` 是否存在且可查询。
  * 已注册 DuckDB source 的 `db_path` 是否存在。
  * 如果路径不一致，输出“需要 metadata/runtime 维护”的明确下一步，而不是自动手写 SQLite。
* 输出结构化环境摘要，供后续 skill 复用：
  * `python_command`
  * `skill_base_dir`
  * `workspace_root`
  * `registry_path`
  * `data_export_ready`
  * `metadata_write_allowed`
  * `recommended_next_skill`

### 3. No Freehand Environment Discovery

在 skill 文档中加入硬规则：

* agent 不应在正式任务中靠多轮 `find/which/python3 -c/import` 自由拼环境。
* 如果环境未初始化或检查失败，应先运行项目环境初始化/doctor skill。
* 缺依赖时应给出初始化/修复指令，不能绕过受控路径直接改 generated/runtime 文件。
* 手写 `runtime/registry.db` 不是常规修复路径。

### 4. Guardrail Tests and Validator as Backstop

validator 和 tests 作为支撑，同时服务于 YAML 标准化：

* 增加测试覆盖：导出 header 中文化不应修改 `fields[].name`。
* 增加 metadata validator 回归：当 dataset 中 `fields[].name` 被批量改成 `display_name/source_field/physical_name` 时 fail 或 strict fail。
* 增加 skill 文档/contract smoke：核心 skill 中应包含“写入范围”和“交接下一 skill”的说明。

### 5. YAML Structure and Content Standardization

将 YAML 标准化纳入 `RA:metadata` 的正式整改范围：

* 明确 dataset YAML 的目标结构：
  * `id/display_name/description/source/business/maintenance/dictionary_refs/mapping_ref/fields/metrics/relationships`
  * 字段只保留 `name`、`physical_name`、`display_name`、`source_field`、`role`、`type`、`description`、`business_definition` 等必要语义。
  * 指标只保留正式可分析指标，要求 `source_field`、`expression`、`aggregation`、`unit`、`valid_grains`、`business_definition.ref` 等关键项。
* 明确 dataset YAML 的内容原则：
  * `description` 是短说明，`business_definition.text` 是结构化定义，二者不得重复。
  * `business_definition.ref` 指向 dictionary/mapping/audit 证据链，不展开 evidence quote 或原始路径。
  * `standard_id` 不能粗暴复用到大量不相关字段；允许粗分类，但需要保持字段自身语义清楚。
  * 字段数量不是越少越好，但 dataset 不应镜像完整物理表；完整物理字段、类型、枚举和样本值属于 runtime/source/profile 层。
* 为 `RA:metadata` 增加输出检查清单：每次正式写 YAML 后，必须说明保留了哪些核心字段/指标、迁出了哪些 profile/evidence/runtime 内容、哪些仍为 pending。
* 提供至少一个高质量 dataset YAML 示例或模板，作为下游项目和 agent 的参考。

### 6. Documentation Scope

文档整改只围绕 skills 使用：

* 不做泛化“开源项目卫生大文档”作为主交付。
* README/INSTALL 只需要链接或简述：用户应先运行 getting-started/doctor 初始化项目环境，再进入具体 skill。
* 重点更新 `skills/*/SKILL.md`、skill references 和必要的 `docs/skill-interaction-design.md`。

## Acceptance Criteria

* [ ] `RA:data-export` 明确：CSV/header/display name 问题在 export layer 解决，不修改正式 metadata YAML。
* [ ] `RA:analysis-run` 明确：分析中发现 metadata 问题只记录 feedback，不直接修 YAML/registry/index。
* [ ] `RA:metadata` 明确：只有用户明确进入 metadata 维护/注册时才允许写正式 metadata 和 sync registry。
* [ ] `RA:metadata-refine` 明确：只生成修正材料，不直接替代 metadata 写入。
* [ ] `RA:getting-started` 或新增 doctor/环境初始化入口能输出当前项目的 Python、skill base、registry、DuckDB path、依赖状态和推荐下一 skill。
* [ ] 环境未初始化、缺依赖、`./scripts/py` 不存在、registry path 不一致时，skill 给出固定下一步，不鼓励 agent 自行绕路。
* [ ] `RA:metadata` 的 YAML 输出标准明确区分 `name`、`display_name`、`physical_name`、`source_field`。
* [ ] dataset YAML 标准明确禁止 profile、enum、source_mapping、expanded evidence、DuckDB type、nullable、registry snapshot、report archive 等跨层内容。
* [ ] 有回归测试或 smoke test 覆盖 `fields[].name` 被批量改成中文展示名的污染。
* [ ] 有高质量 dataset YAML 示例或模板，说明核心字段/指标、正式 metrics、pending 处理和 evidence ref 的写法。
* [ ] PRD 实现后，用户说“取数结果字段名转中文”时，预期路径是 `RA:data-export`，不是 `RA:metadata`。

## Definition of Done

* 核心 skill 文档和必要 references 更新。
* 项目环境初始化/doctor 输出可被后续 skill 复用。
* `RA:metadata` 的 YAML 结构和内容输出标准完成更新。
* metadata validator/test 作为防线覆盖本次误改模式和跨层内容污染。
* 下游 project-local install 后的使用说明仍保持清晰。
* Trellis check 通过。

## Out of Scope

* 不清理 `testkpi` 现有 dirty workspace。
* 不重写全部 README/INSTALL。
* 不做大而全的 repo hygiene 项目。
* 不重构所有 metadata YAML。
* 不把 registry 从 SQLite 迁走。

## Technical Approach

Recommended MVP:

1. Skill-first contract update：
   * 更新 `skills/analysis-run/SKILL.md`
   * 更新 `skills/data-export/SKILL.md`
   * 更新 `skills/metadata/SKILL.md`
   * 更新 `skills/metadata-refine/SKILL.md`
   * 更新 `docs/skill-interaction-design.md`
2. Project environment initialization：
   * 在 `RA:getting-started` 或 metadata/common scripts 下提供只读环境检查。
   * 输出 JSON 环境摘要，后续 skill 按摘要执行。
3. YAML structure/content standardization：
   * 更新 `RA:metadata` 的 YAML 输出契约。
   * 明确 dataset 字段/指标结构、禁止内容和示例模板。
4. Backstop validation：
   * 扩展 metadata validation/test，防止 `fields[].name` 被展示名污染和跨层内容回流。
5. Minimal user-facing docs：
   * README/INSTALL 只补一句入口：先运行 getting-started/doctor，再走分析或 metadata skill。

## Decision (ADR-lite)

**Context**: 用户通过 skills 合理使用 RealAnalyst。事故说明 skills 没有足够清楚地区分“分析/取数展示”和“metadata 维护”，也没有在任务执行前固定项目环境。

**Decision**: 本 task 收窄为 skill-driven guardrails：先修 skill 路由、skill 写入边界、skill 之间交接、项目环境初始化合同，以及 `RA:metadata` 的 YAML 结构和内容标准。validator 和 docs 作为辅助防线。

**Consequences**: 整改范围更小、更贴近事故根因。它不会一次性解决所有仓库卫生问题，但能直接减少用户通过 skills 正常使用时的误判。

## Implementation Plan (Small PRs)

* PR1: Skill contract tightening
  * 更新 `RA:analysis-run`、`RA:data-export`、`RA:metadata`、`RA:metadata-refine`、`RA:getting-started` 的职责边界和交接规则。
* PR2: Project environment initialization
  * 新增/扩展 doctor 或 getting-started 环境检查脚本。
  * 输出固定环境摘要和 recommended next skill。
* PR3: YAML standardization
  * 更新 `RA:metadata` 的 YAML 输出标准和 reference contract。
  * 增加高质量 dataset YAML 示例或模板。
* PR4: Backstop validation and tests
  * 扩展 validator，拦截 `fields[].name` 展示名污染。
  * 添加回归测试。

## Technical Notes

Relevant skill files:

* [skills/analysis-run/SKILL.md](/Users/w/Documents/GitHub/RealAnalyst/skills/analysis-run/SKILL.md)
* [skills/data-export/SKILL.md](/Users/w/Documents/GitHub/RealAnalyst/skills/data-export/SKILL.md)
* [skills/metadata/SKILL.md](/Users/w/Documents/GitHub/RealAnalyst/skills/metadata/SKILL.md)
* [skills/metadata-refine/SKILL.md](/Users/w/Documents/GitHub/RealAnalyst/skills/metadata-refine/SKILL.md)
* `RA:getting-started` skill files should be located during implementation.
* [docs/skill-interaction-design.md](/Users/w/Documents/GitHub/RealAnalyst/docs/skill-interaction-design.md)

Relevant scripts:

* [skills/metadata/scripts/validate_metadata.py](/Users/w/Documents/GitHub/RealAnalyst/skills/metadata/scripts/validate_metadata.py)
* [skills/metadata/scripts/metadata.py](/Users/w/Documents/GitHub/RealAnalyst/skills/metadata/scripts/metadata.py)
* [skills/data-export/scripts/duckdb/export_duckdb_source.py](/Users/w/Documents/GitHub/RealAnalyst/skills/data-export/scripts/duckdb/export_duckdb_source.py)
* [skills/metadata/references/yaml-structure-contract.md](/Users/w/Documents/GitHub/RealAnalyst/skills/metadata/references/yaml-structure-contract.md)
* [skills/metadata/references/maintenance-contract.md](/Users/w/Documents/GitHub/RealAnalyst/skills/metadata/references/maintenance-contract.md)
* [metadata/datasets/demo.retail.orders.yaml](/Users/w/Documents/GitHub/RealAnalyst/metadata/datasets/demo.retail.orders.yaml)

## Open Questions

* 环境初始化入口放在现有 `RA:getting-started`，还是新增一个独立 `RA:doctor` skill/command？
