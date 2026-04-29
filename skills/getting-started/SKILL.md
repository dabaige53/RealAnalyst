---
name: getting-started
description: Use when a user first installs RealAnalyst, asks how to start, needs project initialization guidance, or wants to know what information to prepare before registering datasets or running analysis.
---

# Getting Started

RealAnalyst 从 metadata 开始，不从 SQL 或报告开始。

## First Step

先运行 metadata 初始化：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py init
python3 {baseDir}/skills/metadata/scripts/metadata.py validate
```

然后告诉用户需要准备哪些信息：

| Need | Examples |
| --- | --- |
| Dataset | 名称、来源系统、表、视图、dashboard |
| Fields | 字段名、类型、描述 |
| Metrics | 公式、单位、粒度、业务含义 |
| Evidence | 来源文档、dashboard 备注、SQL、owner 确认 |
| Open questions | 缺失定义、不确定筛选器、review 需求 |

## Choose One Path

1. **使用 demo metadata**：校验 `metadata/datasets/demo.retail.orders.yaml`，再运行 metadata search/context。
2. **注册新数据集**：使用 `metadata` 创建或更新 `metadata/datasets/<source_id>.yaml`。
3. **接入 Tableau 或 DuckDB**：运行 metadata adapter discovery，把脱敏后的同步快照放到 `metadata/sync/<connector>/`，再维护 YAML。

## Handoff

metadata 校验通过后：

```bash
python3 {baseDir}/skills/metadata/scripts/metadata.py index
python3 {baseDir}/skills/metadata/scripts/metadata.py search --type all --query <keyword>
python3 {baseDir}/skills/metadata/scripts/metadata.py context --source-id <source_id>
```

之后再进入 `analysis-plan` 和 `analysis-run`。
