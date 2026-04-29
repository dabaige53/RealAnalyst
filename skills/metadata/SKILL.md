---
name: metadata
description: Use when initializing, registering, refreshing, validating, searching, or packaging LLM-maintained dataset metadata for RealAnalyst; trigger for 数据集注册, 元数据初始化, 指标/字段/术语查询, 业务口径维护, metadata context, Tableau/DuckDB source onboarding, or analysis planning context.
---

# Metadata Skill

RealAnalyst 的统一元数据入口。用它把“数据源发现、业务语义维护、低 token 检索、分析上下文构造”收敛成一条清楚链路。

核心原则：**metadata YAML 是 LLM 维护真源；connector adapter 只提供外部系统素材；registry.db 是运行层；context pack 是本轮分析的最小语义输入。**

## When to Use

使用本 skill：

- 用户要“注册数据集”“初始化元数据”“维护字段/指标/术语”。
- 分析前需要查指标、字段、业务定义、同义词或适用场景。
- 用户提到 Tableau / DuckDB source onboarding，但目标是进入统一元数据体系。
- 需要为 `analysis-plan` 生成小型 metadata context pack，避免直接读取完整 YAML。
- 需要检查 LLM 维护的 YAML 是否满足字段、指标、证据、置信度和 review 契约。

不要使用本 skill：

- 已经进入正式数据导出阶段：Tableau 取数使用 `data-export`，DuckDB 取数使用 `data-export`。
- 用户只要求写报告、做 data profile 或 report verify。
- 用户明确要求操作 Tableau Server 或 DuckDB 运行态脚本本身；此时仍先说明它是 connector adapter，不把它当业务口径真源。

## Operating Model

| 层级 | 职责 | 维护方式 |
| --- | --- | --- |
| YAML | 数据集、字段、指标、术语、业务定义、证据、置信度、review 标记 | LLM 维护 |
| index | 从 YAML 生成的轻量检索记录 | 自动生成 |
| context pack | 本轮分析需要的最小上下文 | 按需生成 |
| connector adapter | Tableau/DuckDB 外部元数据发现与初始化素材 | metadata 调用 |
| registry.db | 执行稳定性与运行时 source 信息 | runtime/connector 维护 |
| OSI | 对外交换语义模型 | 按需导出 |

不要把 connector adapter 当成业务口径真源。Tableau/DuckDB 可以告诉你字段和筛选器有什么，但“这个字段在业务上怎么解释”“这个指标能不能作为确定口径”必须回到 metadata YAML 和 review 标记。

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

更新 `metadata/datasets/*.yaml` 时必须维护：

- dataset identity：`id`、`display_name`、`source.connector`、`source.object`
- business：业务描述、适用/不适用场景、粒度、时间字段
- fields：字段名、角色、类型、描述、业务定义、证据、置信度、`needs_review`
- metrics：指标名、表达式、描述、业务定义、证据、置信度、`needs_review`
- glossary：术语、同义词、定义、证据

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

context pack 是 `analysis-plan` 的正式语义输入。若输出中出现 `needs_review=true` 或 `review_required=true`，必须在计划、报告和验证中标记为推断口径。

## Decision Rules

| 情况 | 动作 |
| --- | --- |
| 用户只给指标/术语，没有 source | 先 `metadata search`，再按候选 source 生成 context |
| 用户给了 source 和指标 | 先 `metadata context --source-id ... --metric ...`，再查 runtime registry |
| index 缺失 | 运行 `metadata validate`，通过后运行 `metadata index` |
| YAML 缺字段/指标定义 | 先补 YAML，设置证据、置信度和 review 标记 |
| Tableau/DuckDB 字段需要刷新 | 读取 `references/connector-adapters.md`，通过 adapter scripts 获取素材 |
| 需要跨系统标准交换 | 使用 `metadata export-osi`；不要新建独立 `osi-export` skill |

## Quality Gates

继续分析前必须满足：

- `metadata validate` 返回 `success=true`。
- `metadata index` 成功生成 `metadata/index/*.jsonl`。
- 需求理解只读取 search/context 结果，不扫完整 YAML。
- `needs_review=true` 不得作为确定口径通过验证。
- `registry.db` 不从 YAML 反写覆盖。
- connector adapter 产出的字段信息必须回填到 YAML 后再被分析流程使用。

## Common Mistakes

| 错误 | 修正 |
| --- | --- |
| 直接读完整 YAML 来理解需求 | 先 search，再 context |
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

## CLI Quick Reference

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py list-commands
python3 {baseDir}/skills/metadata/scripts/metadata.py init
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <query>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --source-id <source_id>
python3 {baseDir}/skills/metadata/scripts/metadata.py inventory
python3 {baseDir}/skills/metadata/scripts/metadata.py export-osi --model-name <model_name>
```
