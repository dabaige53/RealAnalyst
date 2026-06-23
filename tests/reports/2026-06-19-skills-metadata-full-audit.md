# Skills 与元数据全量只读审计报告

## 1. 审计结论与基线

本报告是 `.trellis/tasks/06-19-skills-metadata-full-audit` 的只读审计交付物，覆盖 `skills/` 下 15 个 Skill、`metadata/`、`schemas/`、`runtime/`、`scripts/`、`tests/` 与现有测试报告。审计对象按 PRD 的 6 个维度核查：

1. `SKILL.md` 与构建代码一致性
2. 代码问题
3. Skill 间交付物断档
4. 元数据交付卡点 / 脏内容
5. 测试覆盖
6. 隐藏 bug

本次没有连接 Tableau、DuckDB、MySQL、ClickHouse 或生产凭证；没有修改被审计代码、metadata、schema、测试或既有报告。

自动化基线：

| 覆盖层 | 当前结论 | 证据 |
| --- | --- | --- |
| 项目契约审计 | 本轮执行 `python3 scripts/audit_project_contracts.py`，输出 `success=true`、15 个 Skill、9 个 schema、1 个 dataset、0 warning、0 error | 自动化脚本的 Skill / handoff / metadata / code surface 范围见 `scripts/audit_project_contracts.py:32`、`scripts/audit_project_contracts.py:52`、`scripts/audit_project_contracts.py:110` |
| 既有测试报告 | 2026-06-18 报告记录 `bash test.sh` 已通过，包含 metadata validate/index、项目契约审计、104 个 unittest、manifest workflow regression 和 `git diff --check` | `tests/reports/2026-06-18-project-audit-gates.md:244`、`tests/reports/2026-06-18-project-audit-gates.md:251` |
| 代码覆盖矩阵 | 已把 11 个关键实现面绑定到测试文件和测试报告，但明确不等于每个 helper 都有专项业务测试 | `tests/reports/2026-06-18-code-surface-coverage.md:25`、`tests/reports/2026-06-18-code-surface-coverage.md:58` |
| metadata index 门禁 | 已把 gitignored `metadata/index/` 生成层纳入 `test.sh` 顺序门禁和确定性测试 | `tests/reports/2026-06-18-metadata-index-pipeline.md:13`、`tests/reports/2026-06-18-metadata-index-pipeline.md:18` |

重要边界：自动化层证明“基础契约、文件存在、token handoff、metadata 禁止字段和已登记 code surface 当前全绿”；它不证明每个 Skill 的运行时语义、真实 artifact 内容、最终交付清单、辅助脚本 stdout 契约或跨 Skill 端到端链路都正确。本报告的人工发现集中在这些自动化覆盖不到的地方。

## 2. Skill x 维度覆盖矩阵

标记说明：`A` = 自动化覆盖且当前通过；`M` = 人工核查通过；`F` = 本报告有发现；`G` = 剩余覆盖缺口或需后续专项测试。

| Skill | 1 文档/代码 | 2 代码问题 | 3 handoff | 4 metadata 脏/卡点 | 5 测试覆盖 | 6 隐藏 bug |
| --- | --- | --- | --- | --- | --- | --- |
| `getting-started` | A/M | M | A/M | M | A | M |
| `metadata` | A/M | M | A/M | F | A | G |
| `metadata-search` | A/M | M | M | M | A/G | M |
| `metadata-refine` | A/M | M | M | G | A/G | M |
| `metadata-report` | A/M | M | M | F | A/G | G |
| `analysis-plan` | A/M | M | A/M | M | A | M |
| `analysis-reference` | A/M | M | M | M | A | M |
| `analysis-run` | A/M | M | A/M | M | A | G |
| `reference-lookup` | A/M | M | M | M | A | M |
| `data-profile` | F | F | F | M | F | G |
| `data-export` | A/M | G | A/M | M | A/G | G |
| `data-analytics-semantic-export` | A/M | M | M | M | A/G | G |
| `report` | A/M | M | A/M | M | A | M |
| `report-verify` | F | F | F | M | F | F |
| `artifact-fusion` | F | F | F | M | F | F |

结论：主链路 token 级 handoff 是闭合的，但 `report-verify` 的最终 `delivery_manifest`、`data-profile` 的连续分析回写、`artifact-fusion` 的 lineage/校验与 stdout 契约，仍存在人工发现。

## 3. 人工发现

### P1-1 `delivery_manifest` 绕过 `job_manifest` 用户态真源

- 维度：1、2、3、5、6
- 影响 Skill：`report`、`report-verify`、`analysis-run`
- 影响：`delivery_manifest.json` 可能把旧 artifact index 或目录扫描结果当作最终用户交付清单，绕过 `job_manifest` 的用户可见角色过滤，导致内部文件进入交付核验或真实附件被漏列。
- 证据：
  - 报告输出契约规定用户态产物真源是 `jobs/{SESSION_ID}/job_manifest.json` 的 `user_surface` 与 `user_visible` artifacts：`skills/report/references/output-contract.md:7`、`skills/report/references/output-contract.md:9`
  - 契约进一步规定当前用户态附件清单只应包含报告、显式登记为 `user_attachment` 的附件，`verification.json` 等内部文件不进入清单：`skills/report/references/output-contract.md:21`、`skills/report/references/output-contract.md:25`
  - 输出文件清单系统追加规则要求优先读取 `job_manifest.json` 中 `user_visible=true` 且 role 为 `user_deliverable` / `user_attachment` 的 artifacts：`skills/report/references/output-contract.md:106`、`skills/report/references/output-contract.md:117`
  - 但 `build_delivery_manifest.py` 实际只从 `.meta/artifact_index.json`、根 `artifact_index.json` 和目录扫描取文件：`skills/report-verify/scripts/build_delivery_manifest.py:71`、`skills/report-verify/scripts/build_delivery_manifest.py:87`、`skills/report-verify/scripts/build_delivery_manifest.py:99`、`skills/report-verify/scripts/build_delivery_manifest.py:131`
  - 现有测试 fixture 也只构造 `.meta/artifact_index.json`，未构造 `job_manifest.json` 用户可见 artifacts：`tests/test_metadata_product_fixes.py:677`、`tests/test_metadata_product_fixes.py:687`、`tests/test_metadata_product_fixes.py:713`
- 判断：这是自动化 token handoff 无法发现的语义漂移。脚本能生成 `delivery_manifest.json`，但它没有优先使用新 job 的用户态真源，可能把旧 index 或目录扫描结果当作最终交付清单。
- 修复建议：
  1. `build_delivery_manifest.py` 先读取 `job_manifest.json`，只纳入 `user_visible=true` 且 role 为 `user_deliverable` / `user_attachment` 的 artifacts。
  2. 只有 manifest 缺失时进入 legacy fallback，并在 `delivery_manifest.json` 中明确 `legacy_file_list_fallback`。
  3. 新增测试：manifest 有 report + user_attachment + 内部 profile 时，delivery manifest 只列用户态产物；manifest 损坏时 fail-closed 或明确 legacy。

### P1-2 `artifact-fusion` 声明了 lineage 和 schema 风险，但脚本没有兑现

- 维度：1、2、3、5、6
- 影响 Skill：`artifact-fusion`、`data-export`、`data-profile`、`analysis-run`
- 影响：fusion 输出缺少 lineage、合并策略和 schema 风险标记时，下游 profile/report 仍会继续消费合并结果，但无法追溯输入来源，也无法发现列集合不一致或 manifest 损坏带来的数据解释风险。
- 证据：
  - `SKILL.md` 声明 fusion 要合并 Dataset Pack 并生成统一 manifest：`skills/artifact-fusion/SKILL.md:10`、`skills/artifact-fusion/SKILL.md:12`
  - 前置条件要求输入目录包含 CSV 和 `export_summary.json` / `duckdb_export_summary.json`：`skills/artifact-fusion/SKILL.md:24`、`skills/artifact-fusion/SKILL.md:27`
  - 文档声明 union 要求列名和列数一致：`skills/artifact-fusion/SKILL.md:60`、`skills/artifact-fusion/SKILL.md:65`
  - 文档示例 manifest 包含 `source`、`strategy`、`columns`、`lineage.inputs`、`merged_at`：`skills/artifact-fusion/SKILL.md:98`、`skills/artifact-fusion/SKILL.md:121`
  - README 面向用户承诺“记录输入来源、合并策略和字段处理方式的 manifest”，并称多个输入粒度不一致会暴露风险、不会静默合并：`skills/artifact-fusion/README.md:65`、`skills/artifact-fusion/README.md:70`
  - 实现实际只读 `data.csv` 和可选 `manifest.json`，不校验 `export_summary.json` / `duckdb_export_summary.json`：`skills/artifact-fusion/scripts/fusion.py:31`、`skills/artifact-fusion/scripts/fusion.py:39`
  - manifest JSON 解析失败被静默吞掉：`skills/artifact-fusion/scripts/fusion.py:55`、`skills/artifact-fusion/scripts/fusion.py:60`
  - union 用 `pd.concat(..., sort=False)` 取列并集，没有强制列名/列数一致：`skills/artifact-fusion/scripts/fusion.py:74`、`skills/artifact-fusion/scripts/fusion.py:76`
  - 输出 manifest 只重写 id、created_at、row_count 和 schema，没有写 strategy / lineage.inputs / merged_at：`skills/artifact-fusion/scripts/fusion.py:102`、`skills/artifact-fusion/scripts/fusion.py:115`
  - 脚本运行时先打印 human log，再打印 JSON，stdout 不再是 JSON-only：`skills/artifact-fusion/scripts/fusion.py:23`、`skills/artifact-fusion/scripts/fusion.py:28`、`skills/artifact-fusion/scripts/fusion.py:155`、`skills/artifact-fusion/scripts/fusion.py:156`
- 判断：fusion 是高级但高风险链路；当前实现更像轻量 CSV concat/join，不满足文档里的 Dataset Pack、lineage 和风险暴露契约。下游 `data-profile` 会继续画像，但已经失去输入来源和合并策略证据。
- 修复建议：
  1. 明确 `artifact-fusion` 输入契约：要么改文档承认只支持 `manifest.json + data.csv`，要么实现读取 export summaries。
  2. union 默认 fail-closed：列集合不一致时失败，除非显式 `--allow-column-union`。
  3. 输出 manifest 增加 `source=fusion`、`strategy`、`lineage.inputs`、`merged_at`、输入 row_count/columns。
  4. stdout 改为 JSON-only，日志写到文件或 stderr。
  5. 新增 `tests/test_artifact_fusion.py`，覆盖 schema mismatch、manifest invalid、lineage 输出和 JSON stdout。

### P1-3 `data-profile` 连续分析回写契约没有完整落地

- 维度：1、2、3、5、6
- 影响 Skill：`data-profile`、`report`、`analysis-run`
- 影响：同一 job 多轮 profile 后，下游 report 难以判断哪一份 profile 对应哪一轮 CSV 和分析目的，连续分析可能引用过期画像或丢失本轮用途说明。
- 证据：
  - `SKILL.md` 要求同一 job 多次 profiling 时，必须在 `.meta/artifact_index.json` 与 `job_manifest.json` 写清输入 CSV、产生时间与本轮用途：`skills/data-profile/SKILL.md:74`、`skills/data-profile/SKILL.md:78`
  - 同一段还要求追加分析场景必须更新 `.meta/analysis_journal.md`：`skills/data-profile/SKILL.md:78`
  - 文档推荐 wrapper 将 profiling 产物与输入 CSV 绑定关系回写进 `artifact_index.json` 和 `job_manifest.json`：`skills/data-profile/SKILL.md:81`、`skills/data-profile/SKILL.md:87`
  - `profiling_with_meta.py` docstring 只声明更新 `.meta/artifact_index.json`：`skills/data-profile/scripts/profiling_with_meta.py:2`、`skills/data-profile/scripts/profiling_with_meta.py:9`
  - wrapper 只构造 `profile_manifest` / `profile` items，并调用 `update_artifact_index.py`：`skills/data-profile/scripts/profiling_with_meta.py:120`、`skills/data-profile/scripts/profiling_with_meta.py:157`
  - wrapper 输出不包含 `analysis_journal` 更新，也没有把“本轮用途”写入 manifest 的结构化字段，只保留可选 `note`：`skills/data-profile/scripts/profiling_with_meta.py:128`、`skills/data-profile/scripts/profiling_with_meta.py:142`
  - `update_artifact_index.py` 会把 profile 类 artifact 注册为 `derived_internal`，但 artifact 字段不保留 `input_csv` / `resolved_from` / note：`scripts/update_artifact_index.py:205`、`scripts/update_artifact_index.py:230`、`scripts/update_artifact_index.py:244`
  - 现有专项测试只覆盖 profile artifact role 与用户态隐藏，没有覆盖 wrapper、input_csv 写入 job_manifest 或 analysis_journal：`tests/test_export_profile_manifest_registration.py:39`、`tests/test_export_profile_manifest_registration.py:82`
- 判断：`update_artifact_index.py` 确实会间接把 profile artifact 注册进 `job_manifest`，所以不能说 manifest 完全没更新；但文档承诺的输入 CSV 绑定、本轮用途和 analysis journal 没有完整实现。连续分析里重复画像后，下游 report 难以判断哪一轮 profile 支撑哪一轮分析。
- 修复建议：
  1. 在 job manifest artifact 的 `provenance` / `validation` / `metadata` 字段保留 `input_csv`、`resolved_from`、`profile_run_reason`。
  2. `profiling_with_meta.py` 在 `--note` 或显式参数存在时追加 `.meta/analysis_journal.md`，或把文档改为只承诺 artifact/manifest。
  3. 增加 wrapper 级测试，而不是只测 `update_artifact_index.py`。

### P2-1 自动化覆盖矩阵把“归类”与“专项测试”混在一起

- 维度：5、6
- 影响 Skill：全部 Skill，重点是 `artifact-fusion`、`report-verify/build_delivery_manifest.py`、`data-profile/profiling_with_meta.py`
- 影响：后续维护者可能把“已归类、已问责”误读为“已有行为级测试”，从而不为高风险脚本补参数、stdout、artifact 内容和失败路径测试。
- 证据：
  - 当前 code surface 只列 11 个关键实现面：`tests/reports/2026-06-18-code-surface-coverage.md:25`、`tests/reports/2026-06-18-code-surface-coverage.md:39`
  - 同一报告明确说不声明每个内部 helper 都有专项业务测试：`tests/reports/2026-06-18-code-surface-coverage.md:58`
  - 自动化脚本的 `CODE_SURFACE_CONTRACTS` 不包含 `skills/artifact-fusion/scripts/fusion.py`、`skills/report-verify/scripts/build_delivery_manifest.py` 或 `skills/data-profile/scripts/profiling_with_meta.py`：`scripts/audit_project_contracts.py:110`、`scripts/audit_project_contracts.py:180`
  - `code_file_coverage` 对已被文档提到的 Skill script 主要绑定到 `tests/test_project_contract_audit.py` 与报告，而非专项行为测试：`scripts/audit_project_contracts.py:712`、`scripts/audit_project_contracts.py:716`
- 判断：这不是当前测试失败，而是覆盖表达风险。很多高风险脚本被“已文档化 skill script”覆盖，只能证明文件存在和被 README 问责，不能证明参数、stdout、artifact 内容和边界行为正确。
- 修复建议：
  1. 把 `build_delivery_manifest.py`、`profiling_with_meta.py`、`fusion.py` 提升进 `CODE_SURFACE_CONTRACTS`。
  2. 每个新增 surface 绑定一个 focused test 和测试需求报告。
  3. 在审计 JSON 中区分 `coverage_kind=existence_contract` 与 `coverage_kind=behavior_test`。

### P2-2 metadata sync 历史报告沉积，容易被误读为当前真源

- 维度：4、6
- 影响 Skill：`metadata`、`metadata-report`、`analysis-run`
- 影响：历史 sync report 可能被人工或下游 agent 误读成当前业务口径真源，尤其是在同一 dataset 多份历史报告并存且报告仍包含待补齐项时。
- 证据：
  - `metadata/sync/README.md` 明确 sync 快照只是整理 metadata 的素材，不是最终业务定义：`metadata/sync/README.md:3`、`metadata/sync/README.md:7`
  - 提交规则还说明同步报告中的真实字段/路径不应提交：`metadata/sync/README.md:36`、`metadata/sync/README.md:44`
  - 当前 `metadata/sync/duckdb/reports/` 下有 9 份历史报告；最新样例仍标注“可用但有待补齐”和 2 项待补齐：`metadata/sync/duckdb/reports/20260506_162846_demo.retail.orders_metadata_report.md:7`、`metadata/sync/duckdb/reports/20260506_162846_demo.retail.orders_metadata_report.md:14`
  - 该报告里 `total_revenue` 与 `revenue` 仍是待补齐项：`metadata/sync/duckdb/reports/20260506_162846_demo.retail.orders_metadata_report.md:55`、`metadata/sync/duckdb/reports/20260506_162846_demo.retail.orders_metadata_report.md:60`
- 判断：这不违反自动化禁止字段检查，也不一定是代码 bug；它是 metadata 层面的使用风险。历史 sync report 容易被下游或人工误当“当前报告真源”，尤其当文件多份堆积且内容显示待补齐时。
- 修复建议：
  1. 保留 demo 报告可接受，但应有 README 明确“历史样例，不参与业务真源读取”。
  2. 后续清理时考虑移动到 `metadata/sync/duckdb/reports/examples/` 或统一生成 `metadata/reports/` 最新 dataset-first 报告。
  3. 在 `analysis-run` / `metadata-report` 文档继续强调不得优先读取 sync reports。

### P2-3 demo metadata 仍存在明确业务卡点

- 维度：4
- 影响 Skill：`metadata`、`metadata-report`、`data-analytics-semantic-export`
- 影响：任何基于 demo revenue / total_revenue 的确定性经营结论都必须携带口径 caveat；如果把该 demo 当完整 smoke 数据，当前未决口径会阻断“完全确认”的端到端验收。
- 证据：
  - dataset 维护问题仍在问 revenue 是否含税和运费：`metadata/datasets/demo.retail.orders.yaml:32`、`metadata/datasets/demo.retail.orders.yaml:35`
  - `revenue` 字段 `needs_review=true`，置信度 0.64：`metadata/datasets/demo.retail.orders.yaml:83`、`metadata/datasets/demo.retail.orders.yaml:89`
  - `total_revenue` 指标同样 `needs_review=true`，置信度 0.64：`metadata/datasets/demo.retail.orders.yaml:98`、`metadata/datasets/demo.retail.orders.yaml:103`
  - dictionary 中 `total_revenue` 也保留 `needs_review=true`：`metadata/dictionaries/demo.retail.dictionary.yaml:21`、`metadata/dictionaries/demo.retail.dictionary.yaml:29`
- 判断：这不是脏字段，反而是正确暴露未决口径；但它是当前元数据的真实 blocker。任何使用 demo revenue 做确定结论的报告都必须标注推断口径。
- 修复建议：
  1. 若 demo 数据只作为公共示例，可以保留 `needs_review=true`，但报告和 semantic export 必须持续带 caveat。
  2. 若希望 demo 可用于完全通过的端到端 smoke，应补齐 revenue 口径并同步 dictionary / dataset / index。

## 4. 已核查通过或未发现问题的维度

| 维度 | 结论 |
| --- | --- |
| SKILL.md frontmatter / Completion Summary | 自动化检查覆盖 15 个 `SKILL.md`，当前 0 warning；人工抽查未发现缺失 `name`、`description` 或重复 Completion Summary。 |
| SKILL.md 引用脚本存在性 | 自动化通过，未发现 `SKILL.md` 中引用不存在的 `scripts/*.py`。 |
| 核心 handoff token | `getting-started → metadata → analysis-run → analysis-plan → data-export → data-profile → report → report-verify` 的 token 级 handoff 全部 complete。 |
| metadata 禁止字段 | `metadata/datasets/demo.retail.orders.yaml` 未发现 `sample_values`、`enum_values`、`source_mapping`、`duckdb_type`、`nullable` 等禁止字段。 |
| metadata 引用 | dataset → mapping / dictionary、mapping source_id、dictionary source_evidence 当前未发现断链。 |
| schema JSON | 9 个 schema 当前由自动化检查通过。 |

## 5. 跨 Skill handoff 分析

主链路状态：

| 链路 | 自动化状态 | 人工结论 |
| --- | --- | --- |
| `getting-started → metadata` | complete | 通过。doctor 只读环境摘要、metadata 负责正式维护，边界清楚。 |
| `metadata → analysis-run` | complete | 通过。context / registry / index token 齐全。 |
| `analysis-run → analysis-plan` | complete | 通过。`normalized_request.json` 与 `analysis_plan.md` 契约明确。 |
| `analysis-plan → data-export` | complete | 基本通过。风险在真实 export 参数执行未由本报告 live 验证。 |
| `data-export → data-profile` | complete | token 通过，但多 CSV 时 profile 必须显式 `--data-csv`；wrapper 连续分析回写不完整，见 P1-3。 |
| `data-profile → report` | complete | token 通过，但 profile 多轮来源和本轮用途缺少结构化链路，见 P1-3。 |
| `report → report-verify` | complete | 验证脚本本身有专项覆盖，但 delivery manifest 绕过 `job_manifest` 用户态真源，见 P1-1。 |
| `data-export → artifact-fusion → data-profile` | 未纳入主链路矩阵 | 文档存在，但 fusion 的 lineage/schema/stdout 契约未兑现，见 P1-2。 |
| `metadata → data-analytics-semantic-export` | 不在主链路矩阵 | 只读导出边界清楚；需持续避免把 semantic-layer 副本当 RealAnalyst 真源。 |

## 6. 自动化覆盖 vs 人工覆盖

自动化已覆盖：

- Skill frontmatter、README 输入输出章节、Completion Summary 数量、脚本引用存在性。
- 8 个核心流程 Skill 的 delivery token。
- 核心 handoff 的 producer outputs / consumer inputs / next step / state update token。
- dataset 禁止字段、mapping/dictionary/model/source evidence 基础断链。
- schema JSON 语法。
- code surface 文件 / 测试 / 报告存在性。
- 每个 Python 文件至少进入某种覆盖策略。

人工本次新增覆盖：

- 对 `delivery_manifest` 的真实输入来源做语义核查，而不是只看 `delivery_manifest.json` token 是否出现。
- 对 `artifact-fusion` 的文档承诺、实际 manifest 内容、stdout 契约和 schema 校验做三角核对。
- 对 `data-profile` wrapper 的连续分析回写与下游 report 消费需求做核查。
- 对 `metadata/sync` 历史报告沉积与 demo revenue `needs_review` 做使用风险判断。

仍未完成的覆盖：

- 未跑真实 Tableau / DuckDB / MySQL / ClickHouse 导出；本报告按要求不连接 live 数据源。
- 已执行 `python3 -m unittest tests.test_project_contract_audit`，14 个测试通过。
- 未对本报告发现的 P1 修复项执行代码修复和修复后专项测试；本任务只交付只读审计报告。
- 未逐个执行所有 Skill CLI 的 `--help` 与 happy path；本报告优先核查高风险链路和文件证据。

## 7. 严重级别排序修复清单

| 优先级 | 修复项 | Owner Skill / 文件 | 建议验收 |
| --- | --- | --- | --- |
| P1 | `build_delivery_manifest.py` 改为优先读取 `job_manifest.json` 用户可见 artifacts，legacy fallback 必须显式标记 | `report-verify` / `skills/report-verify/scripts/build_delivery_manifest.py` | 新增测试覆盖 manifest 真源、内部 artifact 排除、legacy fallback warning |
| P1 | 修复 `artifact-fusion` 的 Dataset Pack 输入、schema 校验、lineage manifest、JSON stdout | `artifact-fusion` / `skills/artifact-fusion/scripts/fusion.py` | 新增 `tests/test_artifact_fusion.py`，覆盖 schema mismatch、invalid manifest、lineage、stdout JSON |
| P1 | 补齐 `profiling_with_meta.py` 的 input CSV / 本轮用途 / analysis_journal 回写，或收窄文档承诺 | `data-profile` / `skills/data-profile/scripts/profiling_with_meta.py` | 新增 wrapper 级测试，验证 job_manifest 保留来源绑定、analysis_journal 更新 |
| P2 | 扩展 `CODE_SURFACE_CONTRACTS`，把 `build_delivery_manifest.py`、`profiling_with_meta.py`、`fusion.py` 升为专项实现面 | `scripts/audit_project_contracts.py`、`tests/test_project_contract_audit.py` | 审计矩阵出现新增 surface，且每个 surface 有 focused test 和报告 |
| P2 | 给 `metadata/sync/duckdb/reports/` 历史报告增加“样例/历史，不是真源”边界，或迁移到 examples/archive | `metadata` / `metadata/sync/duckdb/reports/` | `metadata-report` 和 `analysis-run` 不读取 sync report 作为业务口径；README 明确边界 |
| P2 | 决定 demo revenue 是否继续保留 `needs_review=true`；若作为完整 smoke 数据，应补齐口径 | `metadata` / demo dataset + dictionary | `metadata validate`、`metadata index`、metadata report 全部反映一致口径 |

## 8. 本报告自身验证

- 已读取 active task 的 `prd.md`、`design.md`、`implement.md`。
- 已读取 `implement.jsonl` 中列出的全部文件。
- 已执行 `python3 scripts/audit_project_contracts.py`，当前输出为 `success=true`，0 warning，0 error。
- 已执行 `bash test.sh` 全量回归，当前通过：metadata validate/index、项目契约审计、`python3 -m unittest discover -s tests` 的 104 个测试、`scripts/run_manifest_workflow_regression.py` 的 43 个测试和 9 个 subtest、`git diff --check` 均通过。`unittest` 输出中的一次 `user_surface_leakage` failed 是测试用例刻意构造的失败场景，最终测试总结果为 OK。
