# Metadata Lookup Workflow

本文说明统一 `RA:metadata` 入口下的元数据查找流程。目标是在需求理解阶段用轻量、可检索的上下文支撑分析规划，而不是让 agent 直接扫完整元数据文件。

## 四层结构

1. YAML 真源：`metadata/dictionaries/*.yaml`、`metadata/mappings/*.yaml`、`metadata/datasets/*.yaml`

   `dictionaries` 保存公共指标、维度、术语；`mappings` 保存 source 字段到标准语义的映射；`datasets` 只保存真实可分析数据源。LLM 可以维护这些 YAML，但它们仍然是完整定义的真源。

2. 原始证据：`metadata/sources/*`

   用户提供的 Markdown、Excel、connector 抽取报告或迁移输入先归档到这里，其他 YAML 再引用项目内路径作为证据。

3. 轻量索引：`metadata/index/*.jsonl`

   这里保存从 YAML 真源生成的检索记录，例如 dataset、field、metric、mapping、glossary。需求理解阶段先查轻量索引，快速定位可能相关的数据集、字段和指标。

4. 上下文包：`metadata context` 输出 JSON

   当轻量索引命中候选对象后，`metadata context` 会从 YAML 真源抽取小型 JSON 上下文包，供规划阶段读取。上下文包只包含本次分析需要的 dataset、dictionary_refs、mapping_refs、metrics、fields、glossary、mappings、review 提示和缺失对象信息。

## 端到端流程

需求理解阶段不直接读取完整 YAML。推荐流程是先校验真源，再生成索引，再搜索候选对象，最后构造上下文包。

```bash
python3 skills/metadata/scripts/metadata.py validate
python3 skills/metadata/scripts/metadata.py index
python3 skills/metadata/scripts/metadata.py search --type metric --query 收入
python3 skills/metadata/scripts/metadata.py context --dataset-id <dataset_id> --metric <metric>
```

流程含义：

- `metadata.py validate` 校验 YAML 真源是否满足元数据契约。
- `metadata.py index` 将 dictionaries、mappings、datasets 编译成 `metadata/index/*.jsonl`。
- `metadata.py search` 在轻量索引中检索候选 dataset、field、metric、mapping 或术语。
- `metadata.py context` 根据命中的 `dataset_id` 和指标/字段参数，输出可供分析规划读取的 JSON 上下文包。`metadata context` 只接受 `--dataset-id`；runtime/export 阶段才使用 registry 的 `source_id`。

## 当前边界

`registry.db` 是运行层，用于后续运行时锁定数据源，不作为需求理解索引。

Tableau/DuckDB 是 connector adapter。它们提供字段、筛选器、catalog 等初始化素材，但不直接成为业务口径真源。

OSI 是交换层，不进入本地分析主路径。

## 缺失对象反馈

`metadata context` 可以在输出 JSON 中返回 `missing_fields` 或 `missing_metrics`。规划阶段应把这些字段视为拼写错误、未注册对象或元数据缺口的信号，并在继续分析前回到检索或元数据维护流程确认。
