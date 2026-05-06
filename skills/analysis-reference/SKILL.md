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

查询完成后，向用户汇报：

1. 查询了什么类型（template / framework）。
2. 返回了多少条匹配结果。
3. 下一步建议：将查询结果用于当前进行中的 skill（通常是 `RA:analysis-plan`）。
