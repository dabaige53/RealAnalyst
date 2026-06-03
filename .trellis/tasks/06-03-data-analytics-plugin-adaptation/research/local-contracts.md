# RealAnalyst x Data Analytics 本地契约研究

## 范围

对比 RealAnalyst 和 Data Analytics 这两个独立分析系统，并定义一条不修改 Data Analytics 插件的桥接路径。

## 语言要求

- 后续用户回复与交付材料默认使用简体中文。
- 文件路径、命令、函数名、配置键、skill 名、Data Analytics、semantic-layer、user-context、runtime registry、metadata context 等技术名词可保留英文或中英混排。
- 说明应面向产品经理可读：优先讲清边界、输入、输出、风险和验收方式，避免不必要的底层实现展开。

## 来源

- RealAnalyst：`README.md`、`INSTALL.md`、`docs/semantic-analysis-run.md`、`docs/metadata-lookup-workflow.md`、`runtime/README.md`。
- RealAnalyst skills：`RA:metadata`、`RA:analysis-run`、`RA:metadata-report`、`RA:data-export`、`RA:artifact-fusion`。
- RealAnalyst code：`skills/metadata/lib/metadata_context.py`、`skills/metadata/lib/semantic_definitions.py`、`skills/metadata/lib/metadata_osi.py`、`skills/metadata/scripts/export_osi.py`。
- Data Analytics：`index`、`user-context`、semantic-layer setup/template、`product-business-analysis`、`build-report`、`build-dashboard`、`DEPENDENCIES.MD`。
- Data Analytics 当前本地状态：没有保存 source-routing 偏好，也没有注册 semantic layers。

## 方向一致的部分

| 范围 | RealAnalyst | Data Analytics |
| --- | --- | --- |
| Source-backed 工作 | Metadata evidence、runtime registry、job artifacts | Source discovery、verification、source links、source metadata |
| 语义模型 | `metadata/dictionaries`、`mappings`、`datasets`、`metadata context` | 本地 semantic-layer skill，包含 metrics、tables、joins、caveats、query patterns |
| Source 分离 | Metadata 负责含义，registry 负责可执行 source，job 负责单次运行 | Semantic layer 指导 source 选择，实时 source 读取验证结论 |
| 报告质量 | Markdown report、job artifact index、verification | 带 evidence、caveats 和 visual QA 的持久 report/dashboard surface |
| 工具中立 | Codex skills 是第一层 adapter，不是产品边界 | Source lanes 可接入 connectors、pasted SQL、files、screenshots、local code |

## 差异

| 差异 | 风险 |
| --- | --- |
| RealAnalyst 是 project-local；Data Analytics 把 semantic-layer 指针保存在 `$CODEX_HOME/state/plugins/data-analytics/user-context.md`。 | 除非通过 Data Analytics 支持的 state path 注册指针，否则 Data Analytics 不会发现 RealAnalyst context。 |
| RealAnalyst `metadata context` 是每次分析使用的 compact JSON pack；Data Analytics semantic layer 是持久本地 skill。 | 直接使用 context pack 太临时，不适合作为 Data Analytics 的可复用指导。 |
| RealAnalyst runtime registry 可以执行 Tableau/DuckDB/MySQL/ClickHouse exports；Data Analytics 预期通过 source-lane reads 和 verification 工作。 | 除非桥接层暴露可复现的 source 指令或已审阅 extracts，否则 Data Analytics 不应把 RealAnalyst registry 当作 warehouse connector 替代品。 |
| RealAnalyst reports 是 Markdown/job-centered；Data Analytics reports 和 dashboards 有自己的 MCP/HTML/BI 交付契约。 | RealAnalyst reports 应作为 evidence inputs，不应替代 Data Analytics report/dashboard 工作流。 |
| RealAnalyst OSI export 是面向交换的能力，目前标记为不属于本地分析主路径。 | OSI 可以辅助桥接，但不应成为 RealAnalyst 需求理解的主路径。 |

## 桥接方案

### 方案 A：RealAnalyst Semantic-Layer 导出

RealAnalyst 从已验证 metadata 生成 Data Analytics 兼容的本地 semantic-layer skill。

- 输出：`<area>-semantic-layer/SKILL.md`、`references/semantic-layer.md`、`references/source-inventory.md`，以及可选的 `references/evidence.md`。
- 来源：已验证的 `metadata/dictionaries`、`metadata/mappings`、`metadata/datasets`、`metadata index`、runtime status，以及可选的 job/report evidence。
- Data Analytics 注册：可选步骤，需要用户批准后把指针写入 Data Analytics user-context；不修改 Data Analytics 插件。
- 优势：符合 Data Analytics 原生 discovery 机制。
- 劣势：需要新增 RealAnalyst 自己负责的 generator 和 validation。

### 方案 B：OSI 优先交换包

RealAnalyst 导出 `metadata/osi/*.osi.yaml` 和 source inventory，Data Analytics 在创建或刷新 semantic layer 时把它作为一个标准来源。

- 优势：符合 RealAnalyst 已有 exchange 概念。
- 劣势：Data Analytics template 需要 tables、filters、caveats、query patterns、source inventory 和 open questions；单独 OSI 信息太薄。

### 方案 C：Job 交接包

RealAnalyst 从已完成 job 生成交接目录：analysis plan、exported data manifest、profile、report、verification、metadata feedback 和 source inventory。

- 优势：当 Data Analytics 要基于一次已完成的 RealAnalyst run 制作成品级 report/dashboard 时很有用。
- 劣势：如果不配合方案 A，对未来长期 metric lookup 的支持较弱。

## 推荐方向

以方案 A 作为主桥接方案，并把方案 C 作为已完成分析运行的后续桥接能力。

核心思路：RealAnalyst 继续作为项目本地 metadata 和 runtime 执行的来源；Data Analytics 接收一个 source-backed semantic-layer skill，并且这个 skill 遵循 Data Analytics 自己的 template。之后 Data Analytics 把该 skill 用作 source 选择指导，同时在工作流需要时继续执行实时/读取时验证。

## 不可妥协的边界

- 不修改 Data Analytics 插件。
- 不在未获用户批准时，让 RealAnalyst 任意写入 Data Analytics state 路径。
- 不把 `runtime/registry.db` 当作业务语义真源。
- 当 Data Analytics 工作流需要当前数据时，不用 RealAnalyst semantic-layer 输出替代实时 source 读取。
- 不在 RealAnalyst 中复制 Data Analytics report/dashboard 渲染契约。
- 不把凭据、原始客户数据或较长私有 source 摘录复制进生成的 semantic-layer 文件。
- 后续用户回复与交付材料默认使用简体中文。

## 实现形态

新增一条由 RealAnalyst 负责的导出路径，可选形式包括：

- `RA:metadata` 命令：`metadata.py export-data-analytics-layer --area <area> --dataset-id <id> --output <path>`
- 或一个聚焦的 skill：`RA:data-analytics-handoff`。

Generator 应做到：

- 要求先通过 `metadata validate`，并且最好已经执行 `metadata index`。
- 只读取 RealAnalyst 语义真源层和 runtime 状态。
- 生成符合 Data Analytics template 的 semantic-layer skill package。
- 包含 source 优先级、指标定义、粒度、时间规则、filters、tables/source objects、query/export patterns、caveats、freshness expectations 和未决问题。
- 支持 dry-run 和仅输出模式。
- 提供独立的、需要用户批准的 Data Analytics user-context 注册步骤。

## 验收信号

- Data Analytics 工作流可以通过已注册指针发现生成的 semantic-layer skill。
- 后续 agents 可以在实时验证前，从生成层回答“应该使用哪个 metric/table/source？”。
- RealAnalyst metadata validation 仍然负责 schema 和职责边界。
- 桥接方案不修改 Data Analytics 插件文件。
- 生成文件保持紧凑、source-backed，并且在不含敏感材料时可以安全提交。
