# RealAnalyst Agent Instructions

## 核心职责边界

- RealAnalyst 的首要工程原则是职责独立：每个 skill、脚本、目录和文件类型都必须只承担自己的明确职责。
- skills 必须职责独立。一个 skill 不得顺手完成另一个 skill 的主职责；需要交接时，输出交接材料、命令和下一步 owner，而不是跨边界写入。
- 文件体系必须职责独立。数据集定义、字段映射、公共字典、证据材料、审计信息、运行态 registry、检索 index、同步报告、分析报告不得互相复制内容或互相替代。
- 如果某个实现确实需要跨职责读取或写入，必须在对应 skill 文档、脚本说明或报告中明确写出原因、输入来源、输出去向和边界风险。
- 禁止交叉职责污染数据源：不要为了方便把 profile、枚举、mapping、registry、report、分析结论或临时推断塞进正式数据源 YAML。
- 禁止交叉文件污染：一个文件只保存属于该层的内容；发现内容放错层时，应迁回正确层，而不是继续在错误位置追加字段。
- 程序应主动限制职责漂移和无限增长。能用 validate、schema、测试或脚本门禁拦截的，不依赖人工提醒。

## 用户态输出边界

- 普通分析交付、阶段汇报、报告正文和聊天回复默认只展示业务摘要、可查看交付物名称、验证状态、风险和下一步，不展示本地路径、内部目录、脚本名、系统 JSON 文件名、source key、dataset id、profile 文件、审计日志或英文工程字段。
- 技术任务例外：代码实现、测试结果、PR/commit、排障、复跑命令、用户明确要求“路径/文件明细/技术细节/怎么复核”时，可以给必要路径和命令，但必须只给与当前问题相关的最小集合。
- 分析类回复优先从 `job_manifest.json` 的 `user_surface` 和用户可见 artifacts 渲染；`data/`、`profile/`、`.meta/`、`internal/`、`artifact_index.json`、`verification.json` 默认属于内部证据，不进入普通用户清单。
- 报告和普通用户回复不得把内部术语当成解释正文。需要解释系统状态时，用业务化说法，例如“已完成数据画像”“报告已通过验证”，不要写“profile/manifest.json 已生成”“artifact_index 已更新”。
- 技术详情需要保留在报告内时，必须放入显式技术详情段落并通过 report-verify 的技术详情豁免；未标记正文仍按普通用户报告检查。

## Test 测试文档与复跑报告

- 所有 bug 排查、流程调整、输出契约调整、CI/回归门禁调整，在最终修复前必须先写或更新 `Test/` 下的测试文档；不能只在聊天里描述排查过程。
- 测试文档必须包含完整测试需求报告：问题背景、目标行为、风险等级、覆盖范围、数据/环境前提、验收标准、失败路径、复跑命令和实际结果。
- 使用 JavaScript、Node、Playwright、Browser/Chrome 自动化、前端脚本或 CI JS harness 时，必须在测试文档中贴完整 JS 代码和完整 JS 测试代码，不得只写片段、伪代码或“见脚本路径”。
- 如果本次排查没有使用 JS，也必须在测试文档中写明“本次未使用 JS”，说明原因，并列出实际使用的测试代码、命令和复跑方式；能用 JS 复现浏览器、报告渲染、用户态泄漏或 CI 行为时，优先补 JS 复跑脚本。
- 测试文档要能让后续 agent 独立复跑：包含依赖安装、输入 fixture、执行命令、预期输出、失败时定位方式；涉及敏感数据时使用脱敏 fixture，不能写入 token、cookie、真实凭证或完整私有数据。
- 完成修复后，最终回复和 commit summary 要引用对应 Test 文档，并说明哪些测试已经复跑、哪些没有复跑及原因。

## 元数据分层核心准则

- RealAnalyst 的 metadata 不是单个 YAML 仓库，而是分层系统：`datasets` 是语义入口，`mappings` 是字段映射，`dictionaries` 是稳定公共定义，`sources` 是证据和 profile 归档，`audit` 是审计与关联记录，`runtime/registry.db` 是运行态值域和物理结构，`index` 是生成检索层，`reports` 是同步/注册输出。
- `metadata/datasets/*.yaml` 必须保持轻量，只放数据集身份、业务边界、核心字段、核心指标和引用关系；不得把它当 profile store、enum store、mapping copy、registry snapshot 或 report archive。
- dataset 字段和指标只保留必要语义字段：`name`、`physical_name/source_field`、`display_name`、`role`、`type`、`description`、`business_definition`，指标可保留 `expression`、`aggregation`、`unit`、`valid_grains`。
- dataset 禁止写入 `sample_profile`、`sample_values`、`top_values`、`enum_values`、`source_mapping`、`duckdb_type`、`nullable`、`definition_source`，也禁止在字段/指标上直接挂裸 `source_evidence`。
- dataset 字段/指标的 `business_definition` 使用 `ref` 引用 dictionary/mapping/audit 证据链，不展开 `source_evidence`、`quote` 或文档路径；证据链保留在 `metadata/audit`、`metadata/sources`、`metadata/dictionaries` 或 `metadata/mappings`。
- `description` 是短说明，`business_definition.text` 是结构化定义；二者不得完全重复。
- `business_definition.source_type=pending` 表示待补齐，不是正式业务定义；pending candidate 不得进入正式 `metrics`，应留在字段、refine 建议或待补齐清单中。
- `metadata/mappings/*.yaml` 只做源字段到标准语义的映射；空 `definition_override`、候选字段和 profile 观察不应进入 mapping。
- `metadata/dictionaries/*.yaml` 只放稳定公共业务定义；运行态枚举、字段样本值、空 `enum_values: []` 不应放入 dictionary。
- `metadata/sources` 是证据层，可以保存原始文档、profile、data probe、schema snapshot 和 refine evidence；这些内容只被引用，不复制进 dataset 主体。
- `metadata/audit` 是审计层，可以保存变更日志、`business_definition.ref` 关联关系、refine diff、review trail 和历史追溯材料；它不属于分析语义层，不能被 dataset/context/report 当作业务定义真源。
- 当 dataset 通过 `business_definition.ref` 引用 dictionary/mapping/source/audit 证据链时，关联记录写入 `metadata/audit/metadata_relations.jsonl`；不得把关联证据展开复制回 dataset 字段或指标。
- `metadata/sync/reports` 只做同步/注册审计输出，不是业务定义真源；需求理解和分析上下文不得优先读取旧报告。
- `metadata/index` 是生成层，禁止人工编辑；YAML 清理或维护后必须重建 index。
- `runtime/registry.db` 应承接运行态内容：enum values、sample/top values、null rate、distinct count、physical type、nullable、filter candidate values 和取数配置。
- 程序必须主动限制 metadata 无限增长：dataset 超过 1000 行要预警，超过 1500 行要失败；validate 必须检查内容是否放错层，而不只是 YAML 结构合法。

## 元数据报告质量

- 元数据报告必须基于真实元数据、连接器输出、导出 manifest、样本画像、mapping 或 dictionary 证据生成。
- 没有真实内容时，不要用 hard-coded text、placeholder row 或 template sentence 撑版面。
- 某个 section 没有可验证内容时，默认删除该 section；只有在能写出完整、具体、可执行的说明时，才保留该 section。
- 不要输出重复的 generic reminder，例如同一句 usage note 在多行字段或指标中反复出现。
- Report gap 应面向分析师自己维护 metadata：写清需要补哪个 YAML field、补齐后能支持什么分析，不要写“寻求业务确认”“找负责人补定义”这类外部派单措辞。
- 示例值、sample values 和采样结果只能用于识别值域或格式，不得当作完整枚举或业务定义。
- 元数据报告输出前应检查：每个保留的 table row 都有真实来源；每个 note 都能解释具体使用边界；没有证据的内容要么删除，要么标记为明确的元数据待补齐项。
- 未来字段和指标是多样化的，报告逻辑、测试和修复都必须按 metadata 结构、role、definition、expression、mapping、evidence 等通用规则处理；禁止按某个具体业务字段名、指标名或固定中文列名写特例补丁。
- 不得根据 role/status 自动生成字段或指标的“使用建议”“常见用途”句子；如果元数据没有显式维护对应说明，就删除该列。role 只用于分类、筛选入口识别和待补齐影响判断。
<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
