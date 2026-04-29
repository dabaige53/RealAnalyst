---
name: "RA:metadata"
description: Use when initializing, registering, refreshing, validating, searching, or packaging LLM-maintained dataset metadata for RealAnalyst; trigger for 数据集注册, 元数据初始化, 指标/字段/术语查询, 业务口径维护, metadata context, Tableau/DuckDB source onboarding, or analysis planning context.
---

# Metadata Skill

RealAnalyst 的统一元数据入口。用它把“数据源发现、业务语义维护、低 token 检索、分析上下文构造”收敛成一条清楚链路。

核心原则：**sources 是证据层；dictionaries 是公共语义层；mappings 是字段映射层；datasets 只放真实数据源；index/context 是生成层；registry.db 是运行层。**

## When to Use

使用本 skill：

- 用户要“注册数据集”“初始化元数据”“维护字段/指标/术语”。
- 分析前需要查指标、字段、业务定义、同义词或适用场景。
- 用户提到 Tableau / DuckDB source onboarding，但目标是进入统一元数据体系。
- 需要为 `RA:analysis-plan` 生成小型 metadata context pack，避免直接读取完整 YAML。
- 需要检查 LLM 维护的 YAML 是否满足字段、指标、证据、置信度和 review 契约。

不要使用本 skill：

- 已经进入正式数据导出阶段：Tableau 取数使用 `RA:data-export`，DuckDB 取数使用 `RA:data-export`。
- 用户只要求写报告、做 data profile 或 report verify。
- 用户明确要求操作 Tableau Server 或 DuckDB 运行态脚本本身；此时仍先说明它是 connector adapter，不把它当业务口径真源。

## Operating Model

| 层级 | 职责 | 维护方式 |
| --- | --- | --- |
| sources | 用户提供或 connector 产出的原始材料、迁移输入、抽取报告 | 只读归档 |
| dictionaries | 公共指标、公共维度、公共术语、同义词、词表 | LLM 维护 |
| mappings | Tableau/DuckDB/文件字段到标准指标/维度的映射和口径覆盖 | LLM 维护 |
| datasets | 一个真实可分析数据源一个 YAML，包括字段、指标、粒度、时间字段、限制 | LLM 维护 |
| index | 从 YAML 生成的轻量检索记录 | 自动生成 |
| context pack | 本轮分析需要的最小上下文 | 按需生成 |
| connector adapter | Tableau/DuckDB 外部元数据发现与初始化素材 | metadata 调用 |
| registry.db | 执行稳定性与运行时 source 信息 | runtime/connector 维护 |
| OSI | 对外交换语义模型 | 按需导出 |

不要把 connector adapter 当成业务口径真源。Tableau/DuckDB 可以告诉你字段和筛选器有什么，但“这个字段在业务上怎么解释”“这个指标能不能作为确定口径”必须回到 metadata YAML 和 review 标记。

## Directory Contract

维护 YAML 前先按 `references/yaml-structure-contract.md` 判断应该落到哪里：

```text
metadata/
├── sources/        # 原始证据，不直接作为分析上下文
├── dictionaries/   # 公共 metrics / dimensions / glossary
├── mappings/       # source 字段到标准语义的映射和覆盖
├── datasets/       # 一个真实数据源一个 YAML
├── index/          # 自动生成，不手工改
└── sync/           # connector live discovery 素材，按需创建
```

硬规则：

- 不把公共指标、公共维度、术语总表放进 `datasets/`。
- 不把用户给的 Markdown/Excel/抽取报告直接改写成 dataset；先归档到 `sources/`。
- `datasets/` 只放 Tableau view/workbook、DuckDB view/table、CSV/Excel sheet 等可分析对象。
- 真实数据源 YAML 可以引用 dictionaries 和 mappings，但不要复制完整公共字典。

## Core Workflow

### 1. 初始化元数据工作区

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py init
```

用于创建或补齐 `metadata/README.md`、demo dataset YAML、demo model YAML。已有文件默认不覆盖。

### 2. 为外部 source 生成 adapter handoff

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py init-source --backend tableau --source-id <source_id> --dry-run
python3 {baseDir}/skills/metadata/scripts/metadata.py init-source --backend duckdb --source-id <source_id> --dry-run
```

`init-source` 当前输出 connector adapter 执行计划，不直接覆盖 `registry.db`。需要 live connector 发现时，按 `references/connector-adapters.md` 调用保留的 adapter scripts。

### 3. 维护 YAML 语义层

更新 `metadata/dictionaries/*.yaml` 时维护公共：

- `metrics.yaml`：指标 ID、中文名、别名、单位、定义、公式、聚合方式、方向、benchmark。
- `dimensions.yaml`：维度分组、字段 ID、源字段、字段类型、枚举、lookup。
- `glossary.yaml`：业务术语、航司、机场、舱等、周期、同义词。

更新 `metadata/mappings/*.yaml` 时维护：

- `source_id`、`view_field`、`standard_id`、字段/指标类型、口径覆盖、来源证据。

更新 `metadata/datasets/*.yaml` 时必须维护：

- dataset identity：`id`、`display_name`、`source.connector`、`source.object`
- business：业务描述、适用/不适用场景、粒度、时间字段
- fields：数据源内字段、角色、类型、描述、业务定义、证据、置信度、`needs_review`
- metrics：数据源可直接提供或可计算的指标、表达式、证据、置信度、`needs_review`
- references：引用到 dictionaries/mappings 的标准 ID，不复制整套公共口径

### 4. 校验与生成索引

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py index
```

校验失败时不要继续生成 context pack。先修 YAML 的缺字段、重复字段、低置信度 review 标记或证据缺口。

### 5. 低 token 检索

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type metric --query 收入
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type field --query 航班日期
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query 转化率
```

需求理解阶段先查 index，不要直接读取完整 dataset YAML。

### 6. 构造分析上下文

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id> --metric <metric> --field <field>
```

context pack 是 `RA:analysis-plan` 的正式语义输入。若输出中出现 `needs_review=true` 或 `review_required=true`，必须在计划、报告和验证中标记为推断口径。

## Decision Rules

| 情况 | 动作 |
| --- | --- |
| 用户只给指标/术语，没有 dataset | 先 `metadata search`，再按候选 dataset 生成 context |
| 用户给了 dataset 和指标 | 先 `metadata context --dataset-id ... --metric ...`，再用 context 中的 `dataset.runtime_source_id` 查 runtime registry |
| index 缺失 | 运行 `metadata validate`，通过后运行 `metadata index` |
| YAML 缺字段/指标定义 | 先补 YAML，设置证据、置信度和 review 标记 |
| Tableau/DuckDB 字段需要刷新 | 读取 `references/connector-adapters.md`，通过 adapter scripts 获取素材 |
| 需要跨系统标准交换 | 使用 `metadata export-osi`；不要新建独立 `osi-export` skill |
| 用户给了配置抽取文档 | 先保存到 `metadata/sources/`，再拆成 dictionaries/mappings/datasets |

## Quality Gates

继续分析前必须满足：

- `metadata validate` 返回 `success=true`。
- `metadata index` 成功生成 `metadata/index/*.jsonl`，包括 mappings 索引。
- 需求理解只读取 search/context 结果，不扫完整 YAML。
- `needs_review=true` 不得作为确定口径通过验证。
- `registry.db` 不从 YAML 反写覆盖。
- connector adapter 产出的字段信息必须回填到 YAML 后再被分析流程使用。

## Common Mistakes

| 错误 | 修正 |
| --- | --- |
| 直接读完整 YAML 来理解需求 | 先 search，再 context |
| 把公共术语/指标总表放进 `datasets/` | 拆到 `dictionaries/`；`datasets/` 只收真实数据源 |
| 把 source 字段映射塞进公共字典 | 拆到 `mappings/`；字典只放标准语义 |
| 只引用用户 Downloads 里的原始文件 | 复制到 `metadata/sources/` 后再作为证据引用 |
| 把 Tableau/DuckDB 字段名当业务定义 | 字段名只是素材，业务定义写回 YAML |
| 低置信度定义没有 `needs_review=true` | 补 review 标记和证据 |
| 让 YAML 覆盖 `registry.db` | 停止；registry.db 是运行层 |
| 把 OSI 当本地分析主路径 | 停止；OSI 是交换层 |
| 创建新的 connector-specific skill | 停止；把能力接进 metadata adapter |

## Failure Handling

- search 返回 index missing：运行 `metadata validate` 和 `metadata index`。
- context 返回 missing fields/metrics：回到 search 确认拼写，再维护 YAML。
- validate 返回低置信度错误：补证据或设置 `needs_review=true`。
- adapter 脚本失败：修 connector 脚本根因，不手工绕过；失败细节写入初始化报告或分析计划限制项。
- source 冲突：向用户列出候选 dataset、关键字段和适用场景，请用户确认。

## References

- `references/maintenance-contract.md`：元数据五层边界、LLM 维护规则、review 规则。
- `references/connector-adapters.md`：Tableau/DuckDB adapter 的职责、脚本入口和禁止事项。
- `references/yaml-structure-contract.md`：sources/dictionaries/mappings/datasets 的 YAML 结构契约。

## CLI Quick Reference

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py list-commands
python3 {baseDir}/skills/metadata/scripts/metadata.py init
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <query>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py inventory
python3 {baseDir}/skills/metadata/scripts/metadata.py export-osi --model-name <model_name>
```
