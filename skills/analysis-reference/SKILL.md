---
name: "RA:analysis-reference"
description: |
  Use when: (1) Need a specific report template from RealAnalyst references,
  (2) Need a planning framework configuration (logic_path, goal_template, dimension_type_hints).
  Triggers: 查询模板, 查询分析框架, template lookup, framework lookup.
  NOT for metric/field/term lookup — use RA:metadata-search instead.
---

# Analysis Reference Skill

按需查询报告模板和分析框架配置。本 skill 只覆盖 **template** 和 **framework** 两类查询。

本 skill 是高级/流程内查询工具，不放普通用户第一层入口。通常由 `RA:analysis-plan` 或 `RA:report` 调用。

- **metric / field / term / dataset** 查询：使用 `RA:metadata-search`
- **datasource** 查询：使用 `runtime/tableau/query_registry.py`

## 何时使用

- 查报告模板（template）或分析框架（framework）
- 需要 framework 的 `logic_path` / `goal_template` / `dimension_type_hints`
- 需要 machine-readable JSON 结果给 Agent 或脚本继续消费

## 核心流程

```bash
# 查询报告模板
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --template <关键词>

# 查询分析框架（返回单对象契约）
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework <框架名>
```

## 输出契约

- 模板查询：`query` / `type` / `matches` / `count`
- 框架查询命中：`query` / `type` / `found=True` / `framework`
- 框架查询未命中：`query` / `type` / `found=False` / `available_frameworks`

完整示例见 `{baseDir}/skills/analysis-reference/references/output-contract.md`。

## 验证

```bash
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --help
```

## Completion Summary

查询完成后，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已查询类型：<template / framework>
- 命中数量：<count>
- 已返回 machine-readable 结果：<JSON 路径或摘要>

下一步建议：
- 最推荐下一步：/skill RA:analysis-run ...（回到正式分析流程）
- 可选下一步：/skill RA:analysis-plan ...（仅在高级手工规划时）
- 可选下一步：/skill RA:report ...（仅在手工报告写作阶段）

边界提醒：
- 本 skill 只查模板和分析框架，不查字段/指标/术语/dataset。
- 本 skill 没有维护 metadata、执行取数、生成报告或验证交付物。
```
