# brainstorm: lightweight RA skill routing guide

## Goal

把本轮 `grill-me` 确认的 RealAnalyst 产品定位、三核架构、skill 入口层级和完成后的下一步引导整理成可执行需求。后续实现应强化 `RA:getting-started` 的轻量路由职责，统一 README 里的用户入口说明，并让 14 个 RA skills 在完成时给出一致、短小、可执行的下一步提示。

## Product Positioning

RealAnalyst 是一个平台无关的 metadata-first 分析执行系统：用 Metadata 管业务含义，用 Registry 管数据源可执行能力，用 Job 记录单次分析证据链，让 LLM 在可控边界内完成从问题到报告，并把口径缺口反哺回长期资产。

RealAnalyst 不应被定义为 Codex-only skills 套件。Codex skills 只是当前第一套 adapter / entrypoint；核心能力必须能被未来的 CLI、MCP、其他 LLM 产品、企业 agent workflow 或 BI workflow 复用。

## Priority

用户目标优先级：

1. 先服务用户本人高频分析效率。
2. 再沉淀给团队分析师复用。
3. 再上升为企业 agent / BI workflow 基础设施。
4. 最后考虑业务同学自助使用。

第一阶段目标不是一次性全自动分析，而是快速完成一次从问题到报告的正式分析，同时注册必要数据源、字段和口径，并让后续分析可以复用。

## Architecture Principles

### Three Core Model

- Metadata Core：YAML schema、definition state、evidence relation、index/context builder。
- Runtime Registry Core：source registry、Tableau / DuckDB / CSV connector metadata、filter / parameter / source group。
- Job Core：analysis job 状态机、artifact index、feedback、verification artifacts。

核心边界：

- Metadata 管“含义”。
- Registry 管“能不能取”。
- Job 管“这次实际用了什么”。

Report 是 `RA:analysis-run` 面向用户的最终交付，但不是独立 Core。Job 内部保留完整上下文，包括 plan、export、profile、analysis、verification、definition snapshot、feedback 和 artifact index。

### LLM Role

LLM 负责组织、推断、解释和编排；事实状态由 Metadata / Registry / Job 三核承接。

LLM 可以起草定义、组织证据、生成计划、写报告、发现口径缺口和整理 refine 材料，但不能把推断定义直接标成事实，不能隐式写回正式 metadata，不能用聊天记忆替代 job artifacts。

### Controlled Automation

RealAnalyst 做可控自动化分析，不做无边界全自动分析。

关键闸门：

- `RA:analysis-run` 是正式分析入口，不吞掉注册流程。
- 数据未注册时，`RA:getting-started` 应推荐先走 `RA:metadata`。
- LLM 自动补充定义可以进入分析计划和探索分析，但必须先展示给用户看过。
- 正式 metadata 写回必须由用户主动进入维护阶段。
- 分析中发现口径问题时不中断分析，只记录 feedback / refine 线索。

### Asset Quality

资产质量优先于单次报告漂亮。RealAnalyst 的长期护城河是：

- 可复用语义资产。
- 可执行数据源能力。
- 可追溯分析链路。
- 分析后反哺机制。
- 平台无关三核。

### YAML Boundary

YAML 必须分层沉淀，每个 YAML 职责独立。dataset YAML 是轻量语义入口，不是知识库、证据仓库、profile 仓库、枚举仓库、运行态快照或报告归档。

要求：

- `metadata/datasets/*.yaml` 只放数据集身份、可分析字段/指标、边界和引用关系。
- `metadata/dictionaries/*.yaml` 放稳定公共定义。
- `metadata/mappings/*.yaml` 放源字段到标准语义的映射。
- `metadata/sources/` 放原始证据、文档、profile、refine 材料。
- `metadata/audit/` 放变更记录、证据关联和 review trail。
- `metadata/index/` 是生成层，禁止人工编辑。
- `runtime/registry.db` 放运行态事实。

必须通过 validate / schema / tests 干预 dataset YAML 膨胀和职责污染。

### Internal Definition Priority

企业内部口径优先，行业知识用于启动、补充和对照。

优先级：

1. `user_confirmed`
2. `internal_doc`
3. `industry_draft`
4. `llm_inferred`
5. `pending_review`

行业定义不能覆盖内部定义。冲突必须显式记录，进入 feedback / refine，不静默融合。

### Job Boundary

RealAnalyst job 默认是临时分析执行上下文。长期任务管理不放进 Job Core，交给外部 continuity layer，例如 `task-continuity`。

边界：

- RealAnalyst 管分析资产和分析执行。
- `task-continuity` 管长期任务目标、阶段推进和用户意图演进。
- metadata 管长期可复用语义资产。
- job 不承担长期项目管理，不为外部长任务层新增专用接口。

## Skill Routing Decisions

### `RA:getting-started`

定位：轻量向导 + skill router + 最小状态检查。

它可以：

- 识别用户目标。
- 做最小项目状态检查。
- 判断是否已有 metadata / registry / dataset。
- 识别用户给的是 Tableau、DuckDB、CSV、文档或口径说明。
- 在主入口中推荐下一步 skill。
- 输出一条可复制 `/skill` 调用指令。

它不能：

- 创建正式 analysis job。
- 执行取数。
- 生成业务报告。
- 自动注册正式 metadata。
- 自动进入正式分析。

### Primary Entrypoints

普通用户先记 3 个：

| User intent | Skill |
| --- | --- |
| 不知道从哪里开始 | `RA:getting-started` |
| 注册/维护数据源、字段、指标、口径 | `RA:metadata` |
| 数据已准备好，进入正式完整分析 | `RA:analysis-run` |

常见补充入口：

| User intent | Skill |
| --- | --- |
| 查看数据集长期口径说明 | `RA:metadata-report` |
| 分析结束后归档口径问题 | `RA:metadata-refine` |
| 检查已有报告是否可交付 | `RA:report-verify` |

### Flow-internal / Advanced / Compatibility Tools

以下 skills 不进入普通用户第一层入口：

- `RA:analysis-plan`
- `RA:data-export`
- `RA:data-profile`
- `RA:report`
- `RA:metadata-search`
- `RA:artifact-fusion`
- `RA:analysis-reference`
- `RA:reference-lookup`

说明要求：

- `RA:data-export`、`RA:data-profile`、`RA:report` 是流程内能力，通常由 `RA:analysis-run` 编排。
- `RA:analysis-plan` 是流程内计划阶段，不作为主入口。
- `RA:metadata-search` 不放第一层，但 README 要提示“只想查字段/指标/术语/dataset 是否已维护”时可用。
- `RA:artifact-fusion` 是高级多源融合工具，不放第一层。
- `RA:analysis-reference` 是流程内/高级查询工具。
- `RA:reference-lookup` 是 legacy compatibility entrypoint，应弱化用户侧存在感。

## Minimum Registration

当用户想分析但数据未注册时，`RA:getting-started` 应推荐先走 `RA:metadata` 做最小可分析注册，而不是直接推荐 `RA:analysis-run`。

最小可分析 metadata 注册需要满足：

- 有明确 dataset id 和数据源类型。
- 有可用数据获取方式：Tableau / DuckDB / CSV 等。
- 核心字段已识别：时间、主体、维度、指标候选。
- 指标/字段定义有状态：已确认、文档来源、行业草稿、LLM 推断、待确认。
- 本次分析所需字段能被找到。
- 输出本次口径快照/注册摘要，方便用户看过。
- registry / index / context 至少能支持 `RA:analysis-run` 找到数据和口径。

最小注册不是完整治理，而是让一次正式分析可以安全启动。

`RA:metadata` 最小注册完成后，不默认自动生成完整长期 `RA:metadata-report`。它只输出本次口径快照/注册摘要，并必须提示用户如需后续复用，应主动调用 `RA:metadata-report`。

## Metadata Report

`RA:metadata-report` 的主用户是所有使用该数据集做分析的人。它是数据集说明书 / 口径说明书，不只是维护者内部报告。

它不应成为每次最小注册的自动产物，但注册完成后必须提示可生成长期口径说明。

## Feedback And Refinement

产品原则：

分析不中断，维护不断流，正式写回有边界。

流程：

1. `RA:analysis-run` 分析过程中发现 metadata 问题，只记录到 job feedback，不修改正式 YAML。
2. 用户主动调用 `RA:metadata-refine`，把 job feedback、profile、CSV 探查、用户反馈整理并归档成 refine pack。
3. 用户主动调用 `RA:metadata`，基于 refine pack 修改正式 metadata。
4. `RA:metadata` 维护完成后运行 validate / index / sync-registry。
5. 下一次分析复用更好的 metadata。

归档和写回都必须是用户主动动作，不在分析流程中自动偷偷发生。

## Completion Guidance

所有 RA skills 都应在完成时输出统一轻量下一步提示。

统一模板：

```text
完成情况：
- <本 skill 已完成的产物/检查>

下一步建议：
- <最推荐下一步>：/skill RA:xxx ...
- <可选下一步>：/skill RA:yyy ...

边界提醒：
- <必要时说明本 skill 没有自动执行什么>
```

要求：

- 每个 skill 有固定默认下一步映射。
- 最终提示根据本次结果动态裁剪。
- 提示短、明确、可执行。
- 不自动跳转，不自动执行，除非用户明确确认。

示例默认映射：

- `RA:getting-started` → `RA:metadata` / `RA:analysis-run` / `RA:metadata-report` / `RA:metadata-refine` / `RA:report-verify`
- `RA:metadata` → `RA:metadata-report` / `RA:analysis-run`
- `RA:analysis-run` → `RA:metadata-refine` / `RA:report-verify`
- `RA:metadata-refine` → `RA:metadata`
- `RA:metadata-report` → `RA:analysis-run` / `RA:metadata`
- `RA:report-verify` → `RA:metadata-refine` / final delivery

## Documentation Requirements

Need update:

- `README.md`：新用户入口、产品定位、3 个核心入口 + 3 个常见补充入口、流程内 skill 弱化。
- `skills/README.md`：完整 skill 总览前先给入口层级和 skill routing 决策。
- `docs/llm-next-steps.md`：安装后引导中说明 `RA:getting-started` 是默认 skill router。
- `skills/getting-started/SKILL.md`：强化轻量向导 + skill router + 最小状态检查职责。
- 14 个 `skills/*/SKILL.md`：统一 Completion Summary / 下一步提示。

Nice to update:

- `INSTALL.md`：Use It 区轻触，安装后不知道从哪里开始就调用 `RA:getting-started`。
- plugin metadata examples：若当前示例仍暗示所有入口平铺，应同步收口。

## Acceptance Criteria

- [ ] README 第一屏不再平铺全部 skills，而是先讲 3 个核心入口和 3 个常见补充入口。
- [ ] `RA:getting-started` 明确承担 skill router 职责，并限制为轻量检查，不进入正式分析。
- [ ] 未注册数据源的分析请求会被引导到 `RA:metadata` 做最小可分析注册。
- [ ] `RA:analysis-run` 保持正式分析入口边界，不自动吞掉 metadata 注册流程。
- [ ] 流程内 skills 在用户侧被弱化，不作为普通用户主入口。
- [ ] `RA:metadata-search`、`RA:artifact-fusion`、`RA:analysis-reference`、`RA:reference-lookup` 被放入辅助/高级/兼容工具说明。
- [ ] 每个 RA skill 的 Completion Summary 都有统一的下一步提示模板或等价规则。
- [ ] `RA:metadata` 注册完成后提示用户可调用 `RA:metadata-report` 生成长期口径说明，但不自动生成。
- [ ] 文档明确三核架构：Metadata 管含义，Registry 管能不能取，Job 管本次实际用了什么。
- [ ] 文档明确 LLM 不是真实事实源，事实状态由三核承接。
- [ ] 文档明确 dataset YAML 防膨胀和分层沉淀原则。
- [ ] 文档明确 RealAnalyst 不管长期任务管理；长期任务交给外部 continuity layer。
- [ ] 验证通过：相关 Markdown / SKILL 文件格式正常，无明显重复或互相矛盾的入口说明。

## Out Of Scope

- 不新增独立 `skill-router` skill。
- 不实现长期任务管理。
- 不把 `task-continuity` 接入 RealAnalyst job。
- 不改变核心分析执行逻辑。
- 不默认自动生成长期 metadata report。
- 不自动把 refine pack 写回正式 metadata。

## Implementation Notes

- 当前 task 只先整理需求。后续进入实现时，需要先配置 `implement.jsonl` / `check.jsonl`，再按 Trellis Phase 2 走 implement / check。
- 需要注意当前工作区已有其他未提交变更，后续提交时必须只纳入本 task 相关文件。
