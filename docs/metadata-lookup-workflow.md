# Metadata Lookup Workflow

本文说明统一 `RA:metadata` 入口下的元数据查找流程。目标是在需求理解阶段用轻量、可检索的上下文支撑分析规划，而不是让 agent 直接扫完整元数据文件。

## 四层结构

1. YAML 真源：`metadata/dictionaries/*.yaml`、`metadata/mappings/*.yaml`、`metadata/datasets/*.yaml`

   `dictionaries` 保存公共指标、维度、术语；`mappings` 保存 source 字段到标准语义的映射；`datasets` 只保存真实可分析数据源。LLM 可以维护这些 YAML，但它们仍然是完整定义的真源。

2. 原始证据：`metadata/sources/*`

   用户提供的 Markdown、Excel、connector 抽取报告或迁移输入先归档到这里，其他 YAML 再引用项目内路径作为证据。

3. 轻量索引：`metadata/index/*.jsonl` + `metadata/index/search.db`

   这里保存从 YAML 真源生成的检索记录，例如 dataset、field、metric、mapping、glossary。`metadata index` 同时生成 JSONL 文件和 SQLite FTS5 全文索引（`search.db`）。`metadata search` 优先使用 FTS5（BM25 排序），无 `search.db` 时降级到 JSONL 子串匹配。需求理解阶段先查轻量索引，快速定位可能相关的数据集、字段和指标。

4. 数据集目录：`metadata catalog` 输出 JSON

   当数据源尚未确定时，`metadata catalog` 可生成所有数据集的轻量摘要（支持 `--domain` 过滤和 `--group-by domain` 分组），帮助快速浏览可用数据集。

5. 上下文包：`metadata context` 输出 JSON

   当轻量索引命中候选对象后，`metadata context` 会从 YAML 真源抽取小型 JSON 上下文包，供规划阶段读取。上下文包只包含本次分析需要的 dataset、dictionary_refs、mapping_refs、metrics、fields、glossary、mappings、review 提示和缺失对象信息。支持多数据集（multi-dataset）：传多个 `--dataset-id` 可生成合并 context（含共享字典引用和去重术语）。

6. 一致性比对：`metadata reconcile`

   `metadata reconcile` 比对 `runtime/registry.db` 与 metadata YAML 中的指标/维度/术语，输出匹配数、仅运行时存在项、仅元数据存在项、定义不一致项，用于发现语义漂移。

## 端到端流程

需求理解阶段不直接读取完整 YAML。推荐流程是先校验真源，再生成索引，再搜索候选对象，最后构造上下文包。

```bash
python3 skills/metadata/scripts/metadata.py validate
python3 skills/metadata/scripts/metadata.py index
python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
python3 skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
python3 skills/metadata/scripts/metadata.py catalog
python3 skills/metadata/scripts/metadata.py search --type metric --query 收入
python3 skills/metadata/scripts/metadata.py context --dataset-id <dataset_id> --metric <metric>
python3 skills/metadata/scripts/metadata.py context --dataset-id <id_1> --dataset-id <id_2>
python3 skills/metadata/scripts/metadata.py reconcile
```

流程含义：

- `metadata.py validate` 校验 YAML 真源是否满足元数据契约。
- `metadata.py index` 将 dictionaries、mappings、datasets 编译成 `metadata/index/*.jsonl` 和 `metadata/index/search.db`（FTS5）。
- `metadata.py sync-registry` 将通过校验的 dataset YAML 受控同步到 `runtime/registry.db`。
- `metadata.py status` 分别检查 YAML、index、runtime registry 和 export-ready 状态。
- `metadata.py catalog` 生成所有数据集的轻量摘要，支持 `--domain` 过滤。
- `metadata.py search` 在 FTS5 索引中检索候选 dataset、field、metric、mapping 或术语（无 search.db 时降级到 JSONL）。
- `metadata.py context` 根据命中的 `dataset_id` 和指标/字段参数，输出可供分析规划读取的 JSON 上下文包。支持多 `--dataset-id`。`metadata context` 只接受 `--dataset-id`；runtime/export 阶段才使用 registry 的 `source_id`。
- `metadata.py reconcile` 比对 `runtime/registry.db` 与 metadata YAML 的指标/维度/术语差异。

## 当前边界

`registry.db` 是运行层，用于后续运行时锁定数据源、查询运行时指标/维度/术语和管理 source group，不作为需求理解索引。唯一 SQLite 路径是 `runtime/registry.db`。

Tableau/DuckDB 是 connector adapter。它们提供字段、筛选器、catalog 等初始化素材，但不直接成为业务口径真源。

OSI 是交换层，不进入本地分析主路径。

## 缺失对象反馈

`metadata context` 可以在输出 JSON 中返回 `missing_fields` 或 `missing_metrics`。规划阶段应把这些字段视为拼写错误、未注册对象或元数据缺口的信号，并在继续分析前回到检索或元数据维护流程确认。
