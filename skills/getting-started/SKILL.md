---
name: "RA:getting-started"
description: Use when a user first installs RealAnalyst, asks how to start, wants to extract metadata from Tableau/DuckDB/files, or wants to know what information to prepare before registering datasets or running analysis.
---

# Getting Started

RealAnalyst 从抽取和确认 metadata 开始，不从 SQL 或报告开始。

本 skill 是 lightweight guide + skill router + minimal status check。它只识别用户目标、检查当前项目是否已有 metadata / registry / dataset，并输出一条可复制的下一步 `/skill` 指令。

执行前先固定项目环境，不让 agent 自己到处猜：

```bash
python3 {baseDir}/skills/getting-started/scripts/doctor.py --intent start
```

doctor 是只读检查，只输出 JSON：Python 命令、skill base、shared lib、registry path、DuckDB path、依赖状态、metadata / registry / export readiness 和推荐下一 skill。它不创建目录、不安装依赖、不取数、不写 metadata、不写 `runtime/registry.db`。

禁止在本 skill 中：

- 创建正式 analysis job。
- 执行取数。
- 生成业务报告。
- 自动注册正式 metadata。
- 自动进入正式分析。

## First Step

第一步是问清楚用户要做什么，不要先创建目录：

- Tableau workbook / view / dashboard
- DuckDB database / table / view
- CSV / Excel / 其他文件
- 已有 metadata / registry，想进入正式分析
- 已有报告，想做交付前验证
- 已有 job feedback，想归档口径问题
- 暂时没有数据源，只想先整理字段和指标口径

做最小状态检查：

- 先运行 `skills/getting-started/scripts/doctor.py`，以输出中的 `python_command`、`skill_base_dir`、`registry_path` 为本轮固定环境。
- 是否存在 `metadata/datasets/`。
- 是否存在 `runtime/registry.db`。
- 用户是否已经给出 dataset id、source id、Tableau workbook/view、DuckDB path/table、CSV/Excel path/sheet 或业务文档。
- 是否已有本次分析需要的字段、指标和筛选条件。

如果 doctor 报告 `scripts_py_exists=false`、`scripts_py_probe_failed`、`missing_shared_lib`、关键依赖缺失或 registry path 不一致，先让用户按本项目初始化命令修环境；不要切到自由 `which/find/python3 -c/import duckdb` 探测，也不要用 DuckDB CLI 或 `sqlite3` 绕过受控入口。

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
4. **已有 metadata / registry**：推荐进入 `RA:analysis-run` 做正式分析。
5. **只想看长期口径说明**：推荐进入 `RA:metadata-report`。
6. **分析后发现口径问题**：推荐进入 `RA:metadata-refine`。
7. **检查已有报告**：推荐进入 `RA:report-verify`。

只有用户明确同意“保存到项目”时，才创建 `metadata/` 并按新分层写入 `metadata/sources/`、`metadata/dictionaries/`、`metadata/mappings/`、`metadata/datasets/<dataset_id>.yaml`。不要在 getting-started 阶段主动运行 `metadata.py init`。

当用户想分析但数据未注册时，推荐先走 `RA:metadata` 做最小可分析注册，而不是直接推荐 `RA:analysis-run`。

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
/skill RA:metadata-report
帮我查看这个数据集的长期口径说明，列出字段、指标、筛选入口、使用边界和待补齐项。
```

```text
/skill RA:analysis-run
基于已确认 metadata 和 registry，帮我执行正式完整分析。先生成计划并等我确认，再执行取数、画像、分析、报告和验证。
```

```text
/skill RA:report-verify
帮我验证这份报告是否可交付，重点检查数据来源、口径状态、结论证据和待复核项。
```

## Handoff

环境检查入口：

```bash
python3 {baseDir}/skills/getting-started/scripts/doctor.py --intent analyze
python3 {baseDir}/skills/getting-started/scripts/doctor.py --intent metadata
```

元数据抽取并落盘后，再进入 metadata 校验和检索：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <keyword>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --dataset-id <dataset_id>
```

之后再进入 `RA:analysis-run`。`RA:analysis-plan`、`RA:data-export`、`RA:data-profile`、`RA:report` 通常由 `RA:analysis-run` 编排。

## Completion Summary

本 skill 完成时，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已识别用户目标：<从哪里开始 / 注册 metadata / 正式分析 / 口径说明 / refine / verify>
- 已完成最小状态检查：metadata=<有/无>，registry=<有/无>，dataset=<已知/未知>
- 已整理待准备信息：<字段、指标、筛选器、证据、待确认项>

下一步建议：
- 最推荐下一步：/skill RA:metadata ...（数据未注册或字段/指标/口径不足）
- 可选下一步：/skill RA:analysis-run ...（metadata 和 registry 已准备好）
- 可选下一步：/skill RA:metadata-report ... / /skill RA:metadata-refine ... / /skill RA:report-verify ...（仅在用户目标匹配时保留）

边界提醒：
- 本 skill 没有创建正式 analysis job、没有取数、没有生成业务报告，也没有自动注册正式 metadata。
```
