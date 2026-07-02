# RealAnalyst Skill 架构优化说明（2026-07-02）

本文档记录 RealAnalyst skills 的一次架构收敛：把分散的搜索、规划和参考能力合并回 owner skill，把 `data-export` 和 `data-profile` 抽象为共享能力，并补齐轻量数据探索、dashboard-oriented metadata context 和统一路由 hook 的设计约束。

这份文档是 docs-first 说明，面向维护者、Agent builder 和需要评审 skill 改动的人。它不包含私有业务数据，也不要求读者访问 analyst-workspace 的本地任务目录。

---

## 背景问题

旧设计的问题不是能力不够，而是入口太碎：

| 问题 | 表现 | 影响 |
| --- | --- | --- |
| 搜索入口分散 | `metadata` 与 `metadata-search` 同时存在 | 用户和 Agent 不确定该从维护入口还是检索入口开始。 |
| 分析规划独立成 skill | `analysis-run` 需要再调 `analysis-plan` 和 `analysis-reference` | 正式分析链路被拆得过细，产物 owner 变弱。 |
| data-export/data-profile 被描述为流程内阶段 | 它们实际被分析、dashboard、探索和 refine 共同需要 | 文档限制了复用场景，也让输出路径约定不清。 |
| 缺少轻量探索路径 | “先看看数据”容易被升级为正式分析 job | 产生过重 artifacts，降低试探成本。 |
| dashboard 与 metadata 连接不足 | 图表设计容易从页面模块开始，而不是从字段和指标语义开始 | 后续真实数据绑定、筛选器和汇总口径更容易漂移。 |
| hook 路由过窄 | dashboard gate 容易误注入普通分析或 metadata 任务 | 上下文噪声变大，Agent 容易套错 workflow。 |

---

## 优化目标

| 目标 | 判断标准 |
| --- | --- |
| Skill 数量收敛 | 日常 active skillset 从 13 个收敛到 10 个核心入口。 |
| Owner 清晰 | 搜索归 `metadata`，planning 归 `analysis-run`，references 归 `analysis-run/references`。 |
| 共享能力独立 | `data-export` 和 `data-profile` 同时服务分析、dashboard、探索和 refine。 |
| 探索路径轻量 | 快速预览不创建 job，不写正式报告，产物放临时目录。 |
| Dashboard metadata-first | goal decomposer 先读取 dashboard-oriented context，再设计指标、筛选器和图表。 |
| 路由精准 | hook 根据 dashboard、exploration、analysis、metadata 四类场景注入不同上下文。 |

---

## Active Skillset

### 共享层

| Skill | 变化 | 责任 |
| --- | --- | --- |
| `RA:metadata` | 合并 `metadata-search` 的 search/catalog 能力 | 搜索、catalog、注册、维护、validate、index、context、registry sync。 |
| `RA:data-export` | 从 analysis-run 内部阶段改为项目共享能力 | 受控取数、字段白名单、manifest、source lineage。 |
| `RA:data-profile` | 从 analysis-run 内部阶段改为项目共享能力 | 缺失、异常、类型、分布和数据质量画像。 |

### 分析层

| Skill | 变化 | 责任 |
| --- | --- | --- |
| `RA:analysis-run` | 合并 `analysis-plan`，内置 Phase 0.2 planning | 正式分析编排、计划确认、分析 artifacts、连续追问。 |
| `RA:report` | 保持 | 基于证据生成报告。 |
| `RA:report-verify` | 保持 | 验证报告可交付性。 |
| `RA:metadata-refine` | 保持，并可调用共享取数/画像能力 | 生成 metadata 修正参考材料。 |

### Dashboard 层

| Skill | 变化 | 责任 |
| --- | --- | --- |
| `dashboard-goal-decomposer` | 新增 metadata context 准备阶段 | 读取 `metadata context --dashboard-oriented`，拆解目标、指标、维度、筛选器和 chart intent。 |
| `dashboard-prototype-planner` | 保持三段式中间层 | 输出 prototype、layout、view-model contract 和 handoff prompt。 |
| `dashboard-implementation-builder` | 明确调用共享 `data-export` 和 `data-profile` | 构建真实数据 dashboard，完成 binding audit、browser QA 和 review gates。 |

---

## Deprecated 与迁移路径

| Deprecated skill | 新入口 | 迁移说明 |
| --- | --- | --- |
| `RA:metadata-search` | `RA:metadata` | `search`、`catalog`、`context` 都由 metadata 统一承担。 |
| `RA:analysis-plan` | `RA:analysis-run` Phase 0.2 | 正式分析会自动执行 planning；高级维护者不需要单独点名。 |
| `RA:analysis-reference` | `skills/analysis-run/references/` | 框架、模板和 planning reference 改为普通参考文件读取。 |

建议保留 deprecated skill 文件一段时间，文件内只写迁移提示、兼容说明和新入口，不再继续扩展能力。

---

## 共享能力调用约定

### `RA:data-export`

| 调用方 | 输出位置 | 约束 |
| --- | --- | --- |
| `RA:analysis-run` | `jobs/{SESSION_ID}/data/` | 必须来自用户确认后的 analysis plan。 |
| `dashboard-implementation-builder` | `project/<dashboard-name>/warehouse/data/` | 支撑 DWD/DWS/ADS 或 view-model 构建。 |
| 数据探索流程 | `/tmp/exploration_*/` | 默认限制 1000 行以内，标注为临时样本。 |
| `RA:metadata-refine` | refine workbench 或 job 证据目录 | 只用于探查真实字段和值，不直接写 YAML。 |

核心约束保持不变：registry-first、字段白名单、manifest 记录、受控取数、source lineage 可追溯。

### `RA:data-profile`

| 调用方 | 输出位置 | 约束 |
| --- | --- | --- |
| `RA:analysis-run` | `jobs/{SESSION_ID}/profile/` | 作为正式分析证据。 |
| `dashboard-implementation-builder` | dashboard project evidence 或 warehouse profile 目录 | 检查 DWD/ADS 是否支撑页面绑定和筛选器。 |
| 数据探索流程 | `/tmp/exploration_*/profile/` | 快速判断字段类型、空值率、异常和候选问题。 |
| `RA:metadata-refine` | refine reference pack | 为字段定义、枚举、异常和口径缺口提供证据。 |

---

## 数据探索流程

探索流程用于“先看看”“有哪些字段”“数据大概什么情况”这类低承诺请求。

| 步骤 | 行动 | 产物 |
| --- | --- | --- |
| 定位数据源 | `RA:metadata search/catalog` | 候选 dataset、字段、指标和 review 标记。 |
| 快速取数 | `RA:data-export` 限制样本量 | `/tmp/exploration_*/sample.csv` 或等价临时导出。 |
| 快速画像 | `RA:data-profile` | `/tmp/exploration_*/profile/profile.json`。 |
| 输出摘要 | 聊天回复 | 字段列表、样本摘要、分布概览、质量信号、候选问题。 |

探索流程不创建 `jobs/{SESSION_ID}/`，不写正式报告，不沉淀 metadata，不替代可交付分析。它的升级路径只有三种：进入 `RA:analysis-run`、进入 dashboard loop、进入 `RA:metadata-refine`。

---

## Dashboard-oriented Metadata Context

Dashboard 设计需要比普通分析 context 多一些面向图表和控件的提示。

| 字段 | 用途 |
| --- | --- |
| `chart_intent` | 判断指标适合趋势、对比、结构、分布、明细或诊断。 |
| `filter_role` | 判断字段适合作为全局筛选、局部筛选、分组维度或参数。 |
| `aggregation_safety` | 提醒可加总、不可加总、需去重、需按粒度约束的指标。 |
| `view_model_readiness` | 判断字段是否足以进入 dashboard view model，是否需要补口径或真实数据探查。 |

`dashboard-goal-decomposer` 应先读 dashboard-oriented context，再输出 chart contract 和 open questions。`dashboard-implementation-builder` 在真实数据阶段调用共享 `data-export` 和 `data-profile`，并用 binding audit 验证页面控件、模块和数据槽位。

---

## Unified Route Hook

统一路由 hook 的目标不是替代 skill，而是让上下文注入更精准。

| Route | 触发场景 | 注入内容 |
| --- | --- | --- |
| dashboard | dashboard、看板、cockpit、Antigravity HTML、binding audit | Dashboard Loop、三段式 skill 顺序、mock 替换、readiness gates。 |
| exploration | 先看看、快速预览、有哪些字段、数据结构 | 探索约束、临时目录、样本限制、升级路径。 |
| analysis | 正式分析、报告、归因、诊断、对比 | `RA:analysis-run` Phase 0-4、确认点、共享取数画像能力。 |
| metadata | 注册、字段定义、指标口径、registry、context | `RA:metadata` 统一入口、validate/index/sync/context、refine 边界。 |

优先级建议为 dashboard > exploration > analysis > metadata。dashboard 的写入检查和 stop gate 只在明确 dashboard route 时启用，避免普通任务被 dashboard gate 干扰。

---

## 验证建议

| 验证面 | 检查方式 | 通过标准 |
| --- | --- | --- |
| 文档一致性 | 搜索 docs 中旧入口描述 | `metadata-search`、`analysis-plan`、`analysis-reference` 均标注为 legacy 或迁移路径。 |
| Skill 合并 | 检查 `metadata/SKILL.md` 与 `analysis-run/SKILL.md` | search/catalog/context 归 metadata；planning 归 analysis-run。 |
| 共享能力 | 检查 `data-export/SKILL.md` 与 `data-profile/SKILL.md` | 四类调用方都有说明，输出路径清楚。 |
| 探索流程 | 运行一次小样本导出和画像 | 不创建 job，输出临时 profile 和探索摘要。 |
| Dashboard | 运行 dashboard goal 到 implementation 的 contract 检查 | 使用 dashboard-oriented context、真实数据、binding audit 和 browser QA。 |
| Hook | 静态或单元测试 route detection | 四类 route 能正确识别，dashboard gate 不误触发普通分析。 |

本轮本地验证包记录为 23 个检查点通过。公开仓库 PR 如只更新 docs，可把验证范围限定为 markdown 链接、术语一致性和不引入私有路径。

---

## 对维护者的落地顺序

| 顺序 | 动作 | 原因 |
| --- | --- | --- |
| 1 | 先更新 docs 和调用策略 | 让 reviewer 明确架构目标和迁移方向。 |
| 2 | 合并 `metadata-search` 到 `metadata` | 先解决最常见入口分裂。 |
| 3 | 合并 `analysis-plan` 到 `analysis-run` Phase 0.2 | 让正式分析链路恢复单一 owner。 |
| 4 | 将 `data-export` 和 `data-profile` 改为共享能力 | 支撑分析、dashboard、探索和 refine。 |
| 5 | 补探索流程和 dashboard-oriented context | 覆盖轻量预览和可视化链路。 |
| 6 | 引入 unified route hook | 在流程稳定后再做上下文注入自动化。 |

---

## PR 审查重点

| 审查点 | 需要确认 |
| --- | --- |
| 是否只改 docs | 若 PR 标注 docs-first，不应夹带源码、私有任务产物或生成数据。 |
| 是否诚实描述实现状态 | 已落地、目标架构、legacy 兼容和后续代码同步要分清。 |
| 是否保留迁移路径 | 旧入口用户能知道下一步该用哪个 skill。 |
| 是否避免过度自动化 | Hook 只注入上下文和 gate，不替代 skill owner。 |
| 是否保护 source of truth | metadata、registry、job 的边界不因 skill 合并而变模糊。 |
