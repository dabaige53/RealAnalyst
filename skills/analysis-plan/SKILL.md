---
name: "RA:analysis-plan"
description: |
  Use when: (1) Starting a new analysis task and need a formal plan, (2) Need to classify the scenario
  and choose framework, (3) Need to write `.meta/analysis_plan.md` before analysis begins. Triggers:
  分析规划, 场景识别, 框架选择, analysis plan, hypothesis-driven planning, goal decomposition.
---

# Analysis Planning Skill

分析场景识别、框架选择、假设驱动规划与目标拆解。

本 skill 是 `RA:analysis-run` 的流程内规划阶段，不作为普通用户第一层入口。独立调用只适合高级手工编排或排障；如果用户只是想开始一次分析，优先回到 `RA:getting-started` 或 `RA:analysis-run`。

**⚠️ 核心理念：假设驱动分析（Hypothesis-Driven），而非数据驱动分析。**

**⚠️ 另一个核心原则：先确认用户要的是什么报告，再展开分析规划。**

---

## Phase 0: 数据源元数据读取（MUST - 规划前提）

**⚠️ 在开始规划前，必须先了解数据源的可用维度和指标。**

planning 的正式语义输入是 metadata context pack，不得直接读取完整 dataset YAML。context pack 必须来自 `metadata context --dataset-id`，并携带 dataset、dictionary、mapping、glossary 和 review 状态。

若 context 中出现 `review_required=true` / `needs_review=true`，planning 必须将其记录为风险或待确认项。

### 0.0 读取需求画像（MUST）

在开始 planning 前，必须先读取：

- `jobs/{SESSION_ID}/.meta/normalized_request.json`

该文件是本次任务“需求理解”的正式输入，至少用于回答 5 个问题：

1. 这次任务属于哪种 `request_type`
2. 用户真正要解决什么 `business_goal`
3. 报告主要给谁看 `audience`
4. 这次需要多深的展开 `expected_detail_level`
5. 用户偏好什么阅读方式 `output_preference`

**禁止**在未读取 `normalized_request.json` 的情况下直接开始框架选择或模板选择。

**缺失处理**：

- **在 `RA:analysis-run` 编排下**：若 `normalized_request.json` 不存在，报错终止，要求先完成 Step 0.1。
- **用户直接调用 `RA:analysis-plan`**：若 `normalized_request.json` 不存在，向用户追问以下 5 项必填信息，生成一份最小版 `normalized_request.json` 后继续：
  1. `request_type`：这次要做什么类型的分析（监控/汇报/诊断/归因/对标/排名/探索）
  2. `business_goal`：要解决什么业务问题
  3. `audience`：报告给谁看
  4. `expected_detail_level`：需要多深的展开（概览/标准/详细）
  5. `output_preference`：偏好什么阅读方式（结构化报告/简报/仪表盘摘要）

### Metadata 单一来源（非常重要）

业务语义真源统一维护在：

- `metadata/datasets/*.yaml`
- `metadata/mappings/*.yaml`
- `metadata/dictionaries/*.yaml`

planning 的正式输入是 `metadata context` 生成的 context pack；运行取数只通过 `runtime/registry.db` 锁定 source，不把 runtime 当业务配置仓库。

### 0.1 读取数据源元数据配置

当数据源尚未确定时，先运行 `metadata catalog`（可加 `--domain` 过滤）浏览可用数据集摘要，据此选定候选数据源。

当确定数据源后，**必须先读取**对应 dataset 的 metadata context pack，再用 context 中的 `dataset.runtime_source_id` 查询运行 registry。如需同时分析多个数据集，可一次性传多个 `--dataset-id`：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
```

**Source Group 推荐**：确定 primary source 后，查询 `query_registry.py --source <source_key>` 的输出中会包含 `associated_groups`（该 source 参与过的历史数据源组）。如果找到匹配的 group，可在"数据采集方案"中直接推荐复用该 group，用户在确认 plan 时一并通过。也可用 `query_registry.py --groups` 列出所有已有 group。

#### Tableau source

```bash
./scripts/py {baseDir}/runtime/tableau/query_registry.py --source <source_key>
./scripts/py {baseDir}/runtime/tableau/query_registry.py --filter <source_key>
./scripts/py {baseDir}/runtime/tableau/query_registry.py --fields <source_key>
```

运行时正式元数据以 `runtime/registry.db` 查询结果为准，重点读取：

| 字段 | 用途 | 规划应用 |
|------|------|---------|
| `filters` / `parameters` | 可用筛选项与参数 | 只能基于这些字段设计下钻路径 |
| `dimensions` | 维度定义 | 识别维度的业务含义 |
| `measures` | 指标定义 | 确认指标口径，用于假设推演 |
| `grain` / `limitations` | 粒度与限制 | 判断能否支撑当前问题 |

#### DuckDB source

DuckDB source 直接读取 registry 中该 source 的 `spec_json`：

- `dimensions`
- `measures`
- `time_fields`
- `grain`
- `limitations`
- `recommended_usage`

优先读取方式：
- `./scripts/py runtime/tableau/query_registry.py --source <source_id>`
- 必要时，再通过 SQLite store 读取对应 `spec_json`

**示例**：
- Tableau：`example_dashboard` → 可用维度/指标来自 `query_registry.py --source/--filter/--fields`
- DuckDB：`duckdb.example.orders` → 可用维度/指标来自 registry spec

### 0.2 读取业务配置（按需查询）

**⚠️ 禁止直接 read 大型 YAML 文件！必须使用对应 skill 按需查询。**

```bash
# 查询分析框架（获取 logic_path）— 使用 RA:analysis-reference
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework <框架名>

# 查询指标定义（需要时）— 使用 RA:metadata-search
python3 {baseDir}/skills/metadata-search/scripts/search.py --type metric --query <关键词>

# 查询维度定义（需要时）— 使用 RA:metadata-search
python3 {baseDir}/skills/metadata-search/scripts/search.py --type field --query <关键词>

# 查询术语（需要时）— 使用 RA:metadata-search
python3 {baseDir}/skills/metadata-search/scripts/search.py --type term --query <关键词>
```

**示例：查询 MECE 问题树框架**
```bash
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework mece
# 返回完整配置，包括 logic_path、goal_template、dimension_type_hints
```

框架真源见 `{baseDir}/skills/analysis-reference/references/analysis-frameworks.json`；说明文档见 `{baseDir}/skills/analysis-reference/references/analysis-frameworks.md`。`MECE`、`Waterfall`、`OSM`、`Radar` 都应能通过 `--framework` 命中正式框架配置。

### 0.3 构建可用维度/指标清单

基于读取的配置，在规划前必须明确：

```markdown
## 数据源元数据（来自 source spec）

### 可用筛选维度 / 可用分析维度
| 维度 | 类型 | 适合下钻 |
|------|------|---------|
| 区域 | discrete | ✅ |
| 产品 | text | ✅ |
| 日期 | date_range / time_field | ✅ 时间趋势 |
| ... | ... | ... |

### 可用指标
| 指标 | 公式/类型 | 来源 |
|------|-----------|------|
| 收入 | sum(revenue) | measures / registry spec |
| 转化率 | conversions / visits | measures / registry spec |
| ... | ... | ... |
```

补充要求：
- Tableau source：重点看 `filters / dimensions / measures`
- DuckDB source：重点看 `dimensions / measures / time_fields / grain / limitations`
- DuckDB planning 时必须额外写清楚：
  - 推荐时间字段
  - 粒度是否满足问题
  - 指标是原生字段还是后续导出阶段的派生聚合结果

**⛔ 禁止行为**：
- 禁止在不读取 source spec 的情况下开始规划
- 禁止使用 source spec 中未定义的维度进行下钻设计
- 禁止使用 source spec 中未定义的指标进行假设推演

---

## Phase 1: 场景识别（Scenario Classification）

根据 `normalized_request.json` 识别分析场景，不要只靠关键词硬匹配。

### 判断维度

必须综合以下上下文判断：

- `request_type`
- `business_goal`
- `audience`
- `time_scope`
- `comparison_requirement`
- `benchmark_requirement`
- `diagnosis_requirement`
- 数据源本身支持的维度与指标

### 场景、分析模式与框架建议

| 场景 | selected_analysis_mode | 典型用户意图 | 首选框架 |
| --- | --- | --- |
| overview | overview | 要快速看清整体情况或阶段结果 | `mece_issue_tree` |
| ranking | ranking | 要看 Top/Bottom、排序和头尾部差距 | `benchmark_radar` |
| attribution | attribution | 已知有变化，想知道为什么变化 | `waterfall_attribution` |
| metric_planning | overview / exploration | 要把业务目标转成指标体系或看板 | `gsm_metric_planning` |
| funnel | attribution / exploration | 要定位流程或用户旅程转化瓶颈 | `funnel_conversion` |
| cohort | exploration / benchmark | 要比较不同队列的留存、复购或持续贡献 | `cohort_retention` |
| root_cause | attribution | 已知异常，想识别根因和预防动作 | `root_cause` |
| benchmark | benchmark | 要和竞品、目标、基准做差距分析 | `benchmark_radar` |

**识别规则**：
1. 先看 `normalized_request.json` 中的结构化判断
2. 再结合数据源能力判断该场景能否落地
3. 若存在多个候选场景，选择最符合 `business_goal` 的那个
4. 若用户问题天然包含“解释原因”或“判断差距来源”，优先 diagnosis / attribution / benchmark，而不是退回 overview

---

## Phase 1.5: 锁定分析框架、交付方式与报告模板（MUST）

分析框架和 report template 都不是 `RA:report` 阶段才决定的内容，必须在 planning 阶段提前锁定；但**先锁定的应该是分析框架与分析模式，具体报告模板放在最后一步映射**。

**先读取参考**：
- `{baseDir}/skills/analysis-reference/references/analysis-frameworks.md`
- `{baseDir}/skills/report/references/template-system-v2.md`
- `{baseDir}/skills/report/references/template-matrix.md`

**锁定顺序（必须）**：
1. `selected_framework_id`：这次用什么框架拆问题（如 `mece_issue_tree` / `waterfall_attribution` / `gsm_metric_planning`）
2. `selected_analysis_mode`：这次准备怎么分析（overview / ranking / attribution / benchmark / exploration）
3. `selected_delivery_mode`：这次准备怎么呈现（executive_brief / structured_report / diagnosis_report / detailed_report）
4. `selected_report_template`：最终落到哪一个**核心模板 ID**

**alias 处理规则**：
- 若用户明确提到分析框架名（如 `MECE`、`Waterfall`、`OSM`、`Radar`、`funnel`、`cohort`），先用 `RA:analysis-reference --framework` 解析到正式 `selected_framework_id`
- 若用户明确提到旧报告模板名（如 `monthly_analysis`、`dashboard_summary`、`problem_oriented`），先去 `skills/report/references/template-system-v2.md` 的 alias 说明中解析
- plan 中默认写入 `canonical_template` 对应的核心模板 ID，不继续锁旧模板 ID
- 旧模板名只作为用户语言线索和迁移兼容信息保留

**锁定原则**：
- 分析框架必须结合业务问题、目标读者、数据能力和预期决策动作
- 模板选择必须结合 `normalized_request.json`
- 模板选择必须结合分析场景、阅读对象、展开深度、业务目标
- 周期（日/周/月/季/年）默认视为时间范围或例行汇报约束，不应先于问题类型主导选型
- 具体模板只负责呈现与证据编排，不替代分析思路与问题理解
- 一旦写入 `selected_report_template`，后续不得在写报告阶段重新选择模板

**为什么放在业务假设之前**：
- 框架决定问题拆解工具：MECE 看结构，Waterfall 看变化贡献，GSM/OSM 看目标-信号-指标，Funnel 看步骤流失，Cohort 看长期表现，Root Cause 看根因，Benchmark/Radar 看横向差距。
- 假设的深度和呈现方式会被 `selected_framework_id` 与 `selected_delivery_mode` 共同约束：高层一页纸只保留少量关键假设，诊断报告需要完整归因假设，详细报告可以保留更多验证路径。
- 先锁定框架和模板能避免所有 plan 看起来都像同一套假设树。
- 框架锁定不等于先下结论；假设仍必须在后续 Phase 2 中逐条验证。

**必须写入 plan 的字段**：
- `selected_framework_id`
- `framework_selection_reason`
- `selected_analysis_mode`
- `analysis_mode_selection_reason`
- `selected_delivery_mode`
- `delivery_mode_selection_reason`
- `selected_report_template`
- `template_selection_reason`
- `关键证据展示要求`
- `结论级证据块设计`

---

## Phase 2: 业务假设推演（MUST - 禁止跳过）

**⚠️ 这是规划深度的核心，决定了分析质量。**

### 2.1 提出业务假设（3-5 个）

基于用户请求和业务常识，列出可能的原因/增长点/问题点：

**假设生成规则**：
- 每个假设必须是**可验证的**（能用数据证实或证伪）
- 假设要有**业务逻辑支撑**，不能凭空猜测
- 涵盖**内因和外因**两个方向

**假设分类**：
| 类型 | 适用场景 | 示例 |
|------|---------|------|
| 结构假设 | 占比/集中度变化 | "Top3 代理人贡献度下降导致整体下滑" |
| 价格假设 | 收入/利润变化 | "客单价下调导致单位收入下降" |
| 量假设 | 订单/用户/访问变化 | "订单数下降导致收入减少" |
| 竞争假设 | 份额/排名变化 | "竞品促销抢占市场份额" |
| 季节假设 | 同环比异常 | "节假日效应导致同比数据不可比" |

**输出格式**：
```markdown
## 业务假设

### 假设 1: [假设内容]
- **类型**: 结构假设/价格假设/量假设/竞争假设/季节假设
- **业务逻辑**: [为什么这个假设合理]
- **验证方法**: [用什么数据/维度验证]
- **验证指标**: [具体看哪个指标]

### 假设 2: ...
### 假设 3: ...
```

### 2.2 定义异常判定标准

必须基于用户请求、metadata context 中的指标说明、历史业务经验或已确认口径定义量化标准；没有已确认 benchmark 时，必须标记为 planning assumption。

| 判定项 | 来源 | 示例 |
|--------|------|------|
| 波动阈值 | 业务经验 | 波动超过 5% 视为显著变化 |
| 对比基准 | 用户请求/默认同比 | 同比/环比/预算，需说明选择理由 |
| 业务基准 | metadata context / 用户确认口径 | 转化率、留存率、收入达成率等阈值 |

**输出格式**：
```markdown
## 异常判定标准

| 指标 | 优秀 | 良好 | 正常 | 警告 | 来源 |
|------|------|------|------|------|------|
| 转化率 | >12% | 9-12% | 6-9% | <6% | 用户确认/历史经验 |
| 收入达成率 | >100% | 90-100% | 80-90% | <80% | metadata context/用户确认 |

- **波动阈值**: [X]%（超过此值视为显著变化）
- **对比基准**: [同比/环比/预算]
- **选择理由**: [为什么选这个基准]
```

### 2.3 设计下钻路径

**禁止平铺分析所有维度**，必须设计有序的下钻逻辑。

**查询框架的 logic_path**：
```bash
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework <框架名>
# 返回的 logic_path 字段包含下钻阶段定义
```

**输出格式**：
```markdown
## 下钻路径设计

### 路径概览
总量定位 → 结构下钻 → 因子归因

### 详细步骤

| 阶段 | 动作 | 预期输出 | 触发下一步条件 |
|------|------|----------|----------------|
| 1. 总量定位 | 确认整体变化幅度和方向 | 是否达标/异常的判断 | 若异常，进入结构下钻 |
| 2. 结构下钻 | 按空间→实体→时间顺序拆解 | 定位异常集中在哪个维度 | 若定位到具体实体，进入因子归因 |
| 3. 因子归因 | 量/价/结构三因素分解 | 明确驱动因素 | 输出可行动建议 |
```

---

## Phase 3: 框架选择

根据识别的场景选择分析框架，然后使用 `RA:analysis-reference` 查询详细配置。正式框架 ID 必须能被 `query_config.py --framework` 命中：

| 场景        | 首选框架  | 选择理由                     |
| ----------- | --------- | ---------------------------- |
| overview / structure | `mece_issue_tree` | 不重不漏拆解主问题、指标和维度 |
| attribution / variance | `waterfall_attribution` | 逐层解释变化贡献度 |
| metric planning / dashboard | `gsm_metric_planning` | 从目标到信号再到指标 |
| funnel / conversion | `funnel_conversion` | 定位流程步骤和转化瓶颈 |
| cohort / retention | `cohort_retention` | 比较不同队列的持续表现 |
| root cause / anomaly | `root_cause` | 用证据验证根因假设 |
| benchmark / ranking | `benchmark_radar` | 多指标横向对比，识别差距 |

**确定框架后，查询详细配置**：
```bash
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework <框架名>
```

**⚠️ 框架选择必须结合业务问题、目标读者、数据能力和初始假设方向**：选择最能组织后续假设验证的框架，而不是在报告阶段临时补框架。

---

## Phase 4: 分析目标拆解（框架驱动 + 假设驱动）

### 4.1 获取框架配置

使用 `RA:analysis-reference` 查询选定框架的完整配置：

```bash
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework <框架名>
```

返回内容包括：
- `goal_template`：目标模板
- `logic_path`：下钻路径
- `dimension_type_hints`：维度类型识别

### 4.2 目标生成规则

**目标必须围绕假设验证设计**，而非简单套用模板。

| 目标类型 | 生成规则 | 与假设的关系 |
|----------|----------|--------------|
| 固定目标 | 使用 `goal_template.fixed` | 建立分析基础 |
| 假设验证目标 | **新增**：每个假设对应一个验证目标 | 直接验证假设 |
| 维度目标 | 使用 `dimension_goals.pattern` | 支撑假设验证 |
| 交叉目标 | 使用 `cross_goals` | 发现深层关联 |
| 总结目标 | 使用 `goal_template.summary` | 形成结论 |

### 4.3 目标 ID 命名规范

- 固定目标：`goal-1`, `goal-2`, ...
- **假设验证目标**：`goal-hypo-{序号}`（如 `goal-hypo-1`）
- 维度目标：`goal-dim-{维度名}`（如 `goal-dim-代理人`）
- 交叉目标：`goal-cross-{序号}`（如 `goal-cross-1`）
- 总结目标：`goal-summary`

---

**关键证据展示要求**最少要回答：
1. 正文必须展示哪些关键问题数据
2. 哪些表格要直接放进正文
3. 哪些 CSV 只作为附件与追溯

**结论级证据块设计**最少要回答：
1. 每条关键结论下面应该贴哪类问题对象或问题行
2. 哪些证据应该以 TopN / 风险对象表展示
3. 哪些证据只保留在 CSV，不进入正文

---

## Phase 5: 输出 analysis_plan.md（强制结构）

输出路径固定为 `jobs/{SESSION_ID}/.meta/analysis_plan.md`，**必须包含以下 10 个章节**：

1. 需求解析
2. 参数确认
3. 数据源定位
4. 数据源元数据
5. 业务假设
6. 异常判定标准
7. 下钻路径设计
8. 分析框架
9. 分析目标
10. 预期输出

完整模板见 `{baseDir}/skills/analysis-plan/references/plan-template.md`。
goal 的 `artifact` / `filename` / `params` 使用规则见 `{baseDir}/skills/analysis-plan/references/goal-contract.md`。

---

## ⛔ 禁止行为

| 禁止 | 原因 |
|------|------|
| 跳过业务假设直接选框架 | 导致分析缺乏方向性 |
| 使用"该值较高"等模糊描述 | 必须有量化标准 |
| 平铺分析所有维度 | 必须有优先级和下钻路径 |
| 假设验证目标为空 | 每个假设必须对应验证目标 |
| 缺少异常判定标准 | 无法判断"好"与"坏" |

---

## ⚠️ 质量检查点

在输出 analysis_plan.md 前，自检以下内容：

| 检查项 | 要求 |
|--------|------|
| 业务假设 | ≥ 3 个，每个有验证方法 |
| 异常判定标准 | 有波动阈值、对比基准、业务基准 |
| 下钻路径 | 有序，非平铺 |
| 假设验证目标 | 每个假设对应一个 goal-hypo-N |
| 交叉分析目标 | ≥ 2 个 |
| 分析框架 | 已写入 `selected_framework_id` 和 `framework_selection_reason` |
| 分析模式 | 已写入 `selected_analysis_mode` |
| 交付方式 | 已写入 `selected_delivery_mode` |
| 报告模板 | 已写入 `selected_report_template` |
| 证据展示要求 | 已明确正文必须展示哪些关键数据 |
| 结论级证据块 | 已明确关键结论下方应贴哪些问题行/问题对象 |

---

## 注册任务清单

使用 `todowrite` 工具为每个 goal 创建任务项：
- ID 格式：`goal-1`, `goal-hypo-1`, `goal-dim-xxx`, `goal-cross-1`, `goal-summary`
- 状态：`pending`
- **假设验证目标优先级最高**

---

## Goal 契约

- `artifact` / `filename` / `params` 是 plan 对下游输出的正式约束字段
- 优先级规则：`plan 契约 > 行数阈值`
- 排名类与交叉类目标默认需要明确 `artifact: csv`
- `params.top_n` 仅影响报告展示层，不影响 CSV 导出

完整字段定义、示例与使用规则见 `{baseDir}/skills/analysis-plan/references/goal-contract.md`。

## Completion Summary

分析计划完成后，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已生成 `.meta/analysis_plan.md`（10 章）。
- 已锁定数据源、指标、维度、筛选条件、报告模板和待确认项。
- 已记录 source group 推荐和口径风险（如有）。

下一步建议：
- 最推荐下一步：/skill RA:analysis-run ...（确认 plan 后进入正式分析后续 Phase）
- 可选下一步：/skill RA:metadata ...（若 plan 暴露字段/指标/口径缺口）

边界提醒：
- 本 skill 是流程内规划阶段，没有执行取数、画像、报告或验证。
- 本 skill 没有自动注册 metadata；metadata 缺口需回到 /skill RA:metadata。
```
