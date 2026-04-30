---
name: "RA:getting-started"
description: Use when a user first installs RealAnalyst, asks how to start, wants to extract metadata from Tableau/DuckDB/files, or wants to know what information to prepare before registering datasets or running analysis.
---

# Getting Started

RealAnalyst 从抽取和确认 metadata 开始，不从 SQL 或报告开始。

## First Step

第一步是问清楚用户要从哪里抽取元数据，不要先创建目录：

- Tableau workbook / view / dashboard
- DuckDB database / table / view
- CSV / Excel / 其他文件
- 暂时没有数据源，只想先整理字段和指标口径

然后告诉用户需要准备哪些信息：

| Need | Examples |
| --- | --- |
| Source | Tableau workbook/view/dashboard，DuckDB path/table，CSV/Excel path/sheet |
| Fields | 字段名、字段类型、业务含义、是否需要脱敏 |
| Metrics | 指标公式、单位、粒度、业务含义 |
| Filters | Tableau filter/parameter，SQL where 条件，时间范围 |
| Evidence | 来源文档、dashboard 备注、SQL、owner 确认记录 |
| Open questions | 缺失定义、不确定筛选器、是否需要业务 review |

## Choose One Path

1. **Tableau**：先确认 `.env` 是否已填写 Tableau 连接信息，再确认 workbook/view/dashboard 名称，然后做 discovery，抽取字段、筛选器和参数。
2. **DuckDB / 文件数据**：先确认路径、表名或 sheet 名，再抽取字段和样例口径。
3. **手工整理**：先让用户提供字段、指标和业务口径，不创建目录。

只有用户明确同意“保存到项目”时，才创建 `metadata/` 并按新分层写入 `metadata/sources/`、`metadata/dictionaries/`、`metadata/mappings/`、`metadata/datasets/<dataset_id>.yaml`。不要在 getting-started 阶段主动运行 `metadata.py init`。

## Teach Skills

用户问“怎么用”时，给这些快捷入口：

```text
/skill RA:metadata
帮我整理这个数据源的字段、指标、筛选器和业务口径。先问我要哪些材料，不要直接创建文件。
```

```text
/skill RA:metadata
帮我整理这些指标：名称、公式、单位、粒度、业务含义、来源证据和待确认问题。
```

```text
/skill RA:metadata
帮我整理术语表：中文名、英文名、同义词、定义、来源证据和 review 状态。
```

```text
/skill RA:analysis-plan
基于已确认 metadata，帮我生成分析计划，先列出数据源、指标、维度、筛选条件和风险。
```

```text
/skill RA:analysis-run
基于已确认 metadata 和分析计划，帮我执行取数、画像、分析和报告，并保留证据路径。
```

## Handoff

元数据抽取并落盘后，再进入 metadata 校验和检索：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <keyword>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
```

之后再进入 `RA:analysis-plan` 和 `RA:analysis-run`。

## Completion Summary

本 skill 任务完成后，向用户汇报：

1. 确认了哪种数据源类型（Tableau / DuckDB / CSV / Excel / 手工整理）。
2. 列出了哪些待准备信息（字段、指标、筛选器、证据、待确认项）。
3. 下一步建议：进入 `/skill RA:metadata` 开始注册和整理元数据。
