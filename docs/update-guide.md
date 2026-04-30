# RealAnalyst 内容物更新指南

本文档供用户交给 LLM / Codex 执行。目标是先把 RealAnalyst 插件本体更新到当前版本，再对照最新架构逐层检查和更新已安装项目中的内容物，使其完全适配最新版本。

> **执行原则**：先汇报再执行；缺失项引导用户补充，不自动创建业务内容。涉及写入项目内容或 registry 的动作，先展示将要变更的内容，用户确认后再执行。每完成一类检查后向用户汇报完成了什么、发现了什么问题，并提醒进入下一步。

---

## 第 0 步：更新插件本体并读取架构基线

先在目标项目中重新运行安装器，确保 `~/plugins/realanalyst`、当前项目 `.agents/skills/` 和 `runtime/` 执行支持文件都是最新版本：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 -
```

如果用户只想刷新插件仓库和 marketplace，不覆盖项目内 `.agents/skills/`：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --skip-project-skills
```

如果用户明确不希望安装或更新项目内 `runtime/` 支持文件：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --skip-project-runtime
```

安装器默认会更新项目内 `runtime/` 支持文件，但不会复制 `registry.db`、缓存、本地生成数据，也不会创建 `metadata/`、`jobs/`、`logs/` 或业务工作区内容。

安装完成后必须读取 installer 输出里的 `Installed plugin version` 和 `Installed plugin commit`。如果用户明确要求某个版本（例如 `0.3.1`），但实际版本或 commit 不匹配，先停止并说明版本未对齐，不要继续做后续适配检查。

先读取以下 RealAnalyst 架构文档建立上下文，不要跳过。优先读取线上 raw URL；如果网络不可用，再读取插件仓库 `~/plugins/realanalyst/` 下的同名文件。不要去目标业务项目根目录查找这些仓库文档。

| 文档 | 了解什么 |
| --- | --- |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/architecture.md` | 双主线架构（注册元数据线 + 实施分析线）、文件职责 |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/skill-interaction-design.md` | 11 个 skill 的调用关系、数据契约、运行时序 |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/skills/README.md` | 完整 skill 清单、后端脚本速查、目录结构 |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/repository-layout.md` | 目录边界和 Git 策略 |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/skills/metadata/SKILL.md` | metadata skill 的分层模型、Core Workflow 和 Decision Rules |

读完后向用户确认：「已更新插件本体并读取架构基线，准备开始逐层检查。」

---

## 第 1 步：元数据 YAML 层

检查 `metadata/` 目录下是否存在必需的 YAML 文件。

### 1.1 目录结构

```bash
ls metadata/sources/ metadata/dictionaries/ metadata/mappings/ metadata/datasets/ metadata/models/ 2>/dev/null
```

期望：
- `metadata/sources/` — 至少一个原始证据或说明文件
- `metadata/dictionaries/` — 至少一个公共语义 YAML（指标/维度/术语）
- `metadata/mappings/` — 至少一个字段映射 YAML（如果有 source onboarding）
- `metadata/datasets/` — 至少一个真实数据源 YAML

### 1.2 YAML 结构合规

对每个 dataset YAML 检查是否包含：

| 模块 | 必填 |
| --- | --- |
| Dataset identity | `id`、展示名、来源系统、对象名 |
| Business context | 适用场景、不适用场景、粒度、时间字段 |
| Fields | 字段名、角色、类型、业务定义、证据、置信度、review 状态 |
| Metrics | 指标公式、单位、粒度、业务含义、证据、置信度、review 状态 |
| Glossary | 术语、同义词、定义、证据 |
| dictionary_refs | 引用的公共字典列表 |
| mapping_refs | 引用的字段映射列表 |

完整 YAML 结构见 `skills/metadata/references/yaml-structure-contract.md`。

### 1.3 缺失处理

如果缺少任何 YAML 文件或必填模块：

1. 列出具体缺失项（如「缺少 metadata/datasets/ 下的数据源 YAML」）。
2. 引导用户提供信息：数据源名称、关键字段、指标定义、业务含义。
3. **不要猜测业务内容**，只创建包含占位符的模板并标记 `needs_review: true`。

### 1.4 校验

```bash
python3 skills/metadata/scripts/metadata.py validate
```

✅ 汇报：检查了多少个 YAML、多少通过、多少失败、具体失败原因。
➡️ 下一步：第 2 步索引层。

---

## 第 2 步：索引层

### 2.1 生成索引

```bash
python3 skills/metadata/scripts/metadata.py index
```

期望输出：
- `metadata/index/*.jsonl` — JSONL 检索记录
- `metadata/index/search.db` — SQLite FTS5 全文索引

### 2.2 验证索引

```bash
python3 skills/metadata/scripts/metadata.py catalog
python3 skills/metadata/scripts/metadata.py search --type all --query <任意已知指标名>
```

确认：
- `catalog` 能列出所有数据集摘要
- `search` 使用 FTS5 后端（输出中应体现 BM25 排序），如无 search.db 则降级到 JSONL

### 2.3 缺失处理

如果 `index` 命令失败：先回第 1 步修复 YAML，再重新 index。

✅ 汇报：生成了多少条索引记录，search.db 是否创建成功，catalog 列出了多少数据集。
➡️ 下一步：第 3 步运行时层。

---

## 第 3 步：运行时层

### 3.1 同步 registry

```bash
python3 skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
```

如果 status 显示 registry 未同步：

```bash
python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
```

先把 dry-run 输出中的新增、覆盖、冲突和失败项展示给用户。只有用户确认后，才执行正式同步：

```bash
python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
```

对每个 dataset 重复执行。

### 3.2 验证运行时查询

```bash
python3 runtime/tableau/query_registry.py --source <source_id>
python3 runtime/tableau/query_registry.py --groups
```

确认：
- `--source` 输出包含 `associated_groups` 字段
- `--groups` 能列出已有 source group（如无 group 则空列表正常）

### 3.3 Context 验证

```bash
# 单数据集
python3 skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>

# 多数据集（如有多个 dataset）
python3 skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
```

确认：
- 单数据集 context 正常输出
- 多数据集 context 包含 `shared_dictionary_refs` 和 `shared_glossary`

### 3.4 一致性比对

```bash
python3 skills/metadata/scripts/metadata.py reconcile
```

确认：输出每个类别（metrics / dimensions / glossary）的匹配数、不一致项。如有不一致，列出具体差异项引导用户修补。

### 3.5 .env 配置

如果用户需要 Tableau 连接：

```text
检查 ~/plugins/realanalyst/.env 是否已配置：
TABLEAU_BASE_URL=
TABLEAU_SITE_ID=
TABLEAU_PAT_NAME=
TABLEAU_PAT_SECRET=
```

缺失时引导用户填写，**不要在聊天中暴露密钥**。

✅ 汇报：registry 同步状态、source group 数量、context 生成情况、reconcile 差异数。
➡️ 下一步：第 4 步 skill 能力验证。

---

## 第 4 步：Skill 能力验证

逐项验证当前架构的关键能力是否可用：

| 能力 | 验证命令 | 期望 |
| --- | --- | --- |
| FTS5 搜索 | `python3 skills/metadata/scripts/metadata.py search --type all --query <keyword>` | 使用 search.db，BM25 排序 |
| 数据集目录 | `python3 skills/metadata/scripts/metadata.py catalog` | 列出所有数据集摘要 |
| 域过滤目录 | `python3 skills/metadata/scripts/metadata.py catalog --domain <domain>` | 只列出指定域数据集 |
| 多数据集 context | `python3 skills/metadata/scripts/metadata.py context --dataset-id <a> --dataset-id <b>` | 输出合并 context |
| 一致性比对 | `python3 skills/metadata/scripts/metadata.py reconcile` | 输出匹配/不一致统计 |
| source group 查询 | `python3 runtime/tableau/query_registry.py --groups` | 列出 source group |
| source group 关联 | `python3 runtime/tableau/query_registry.py --source <id>` | 输出含 associated_groups |
| artifact-fusion | 检查 `skills/artifact-fusion/SKILL.md` 存在 | skill 已安装 |

如有命令报错，记录错误信息，判断是缺失依赖、缺失数据还是代码问题，给出修复建议。

如果生成 metadata report 或 review gap report，额外确认报告中没有旧列名 `Schema 说明`，也没有把 `schema_note` 中“字段存在于 DuckDB/Tableau 对象...”这类技术旁注展示为业务说明。报告应展示 `business_definition.text`、定义来源、证据和 review 状态。

✅ 汇报：哪些能力通过、哪些失败、具体错误。
➡️ 下一步：第 5 步文档层。

---

## 第 5 步：文档层

检查文档时要区分两类位置：

- **RealAnalyst 仓库文档**：读取线上 raw URL，或插件仓库 `~/plugins/realanalyst/` 下的同名文件。
- **目标项目文档**：只检查安装器实际写入的 `runtime/README.md`、`runtime/tableau/README.md`，以及用户确认创建后的 `metadata/README.md`。业务项目不是完整 RealAnalyst repo，缺少根 `README.md` 或 `docs/*.md` 是正常情况，不要当作待修复问题。

检查以下文档是否反映了当前架构（FTS5、catalog、source group、artifact-fusion、reconcile、多数据集 context）。

### 需要检查的文件

| 文件 | 关键词应存在 |
| --- | --- |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/README.md` | FTS5、catalog、source group、reconcile、多数据集 |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/architecture.md` | search.db、catalog、reconcile、source_groups |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/metadata-lookup-workflow.md` | FTS5、catalog、reconcile、multi-dataset |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/metadata-conversion-flow.md` | search.db、catalog、reconcile |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/semantic-analysis-run.md` | FTS5、catalog、reconcile、source_groups |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/skills/README.md` | FTS5、source group、reconcile |
| `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/skills/metadata/README.md` | FTS5、catalog、reconcile、multi-dataset |
| `runtime/README.md`（目标项目） | source_groups、--groups |
| `runtime/tableau/README.md`（目标项目） | source_groups、--groups |
| `metadata/README.md`（仅当目标项目已创建 metadata） | search.db、catalog、reconcile |

如果 RealAnalyst 仓库文档缺少关键词，说明它可能未更新到最新架构。列出缺失项，但**不要自动改写文档内容**——让用户确认后再更新。目标项目缺少未创建的业务文档时，只报告“尚未创建”，不要建议补齐完整仓库文档。

✅ 汇报：哪些文档已是最新、哪些需要更新、具体缺失什么。
➡️ 下一步：第 6 步总结。

---

## 第 6 步：总结汇报

完成所有检查后，向用户输出一份结构化汇总：

```
## 更新检查结果

### ✅ 已通过
- [列出通过的项]

### ⚠️ 需要用户补充
- [列出需要用户提供信息才能修复的项]

### 🔧 已自动修复
- [列出本次执行中自动修复的项（如 index 重建、registry 同步）]

### ❌ 需要人工处理
- [列出需要人工介入的项（如 YAML 业务定义缺失、.env 未配置）]

### 下一步建议
- [根据检查结果给出 1-3 条最重要的下一步行动]
```
