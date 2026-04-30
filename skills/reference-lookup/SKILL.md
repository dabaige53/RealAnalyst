---
name: "RA:reference-lookup"
description: |
  Use when: (1) Need a specific template/term/metric/dimension from RealAnalyst metadata or references,
  (2) Need planning reference lookup, (3) Need a small lookup result instead of reading large files directly.
  Triggers: 查询模板, 查询术语, 查询指标定义, 查询分析框架, 查询维度定义, template lookup, glossary lookup, metric definition, framework lookup, dimension lookup.
---

# Reference Lookup Skill

按需查询 metadata index、registry lookup tables 和报告模板参考文件。

- `metric` / `dimension` / `glossary`：优先读取 metadata index；运行层只服务取数。
- `template` / `framework`：读取 skill references，不把 runtime 当业务配置仓库。


## 何时使用

- 查报告模板、业务术语、指标定义、分析框架、维度定义
- 需要 framework 或模板选择参考
- 需要 machine-readable JSON 结果给 Agent 或脚本继续消费

## 边界

- 本 skill 只覆盖 `template` / `glossary` / `metric` / `framework` / `dimension` 五类配置查询
- datasource 查询请使用 `{baseDir}/runtime/tableau/query_registry.py`
- `query_registry.py` 仅作为 datasource 查询入口说明，**不属于本 skill 的输出契约**
- 不要把 runtime 当业务语义真源；语义维护回到 `RA:metadata`
- 如需模板细节，读取 `skills/report/references/template-system-v2.md`

## 核心流程

```bash
# 查询列表类配置（统一返回 query/type/matches/count）
python3 {baseDir}/skills/reference-lookup/scripts/query_config.py --template <关键词>
python3 {baseDir}/skills/reference-lookup/scripts/query_config.py --glossary <关键词>
python3 {baseDir}/skills/reference-lookup/scripts/query_config.py --metric <关键词>
python3 {baseDir}/skills/reference-lookup/scripts/query_config.py --dimension <关键词>

# 查询框架（返回单对象契约）
python3 {baseDir}/skills/reference-lookup/scripts/query_config.py --framework <框架名>
```

## 输出契约

- 列表类查询：`query` / `type` / `matches` / `count`
- 框架查询命中：`query` / `type` / `found=True` / `framework`
- 框架查询未命中：`query` / `type` / `found=False` / `available_frameworks`

完整示例见 `{baseDir}/skills/reference-lookup/references/output-contract.md`。

## 验证

```bash
python3 {baseDir}/skills/reference-lookup/scripts/query_config.py --help
```

## Completion Summary

查询完成后，向用户汇报：

1. 查询了什么类型（template / metric / glossary / dimension / framework）。
2. 返回了多少条匹配结果。
3. 下一步建议：将查询结果用于当前进行中的 skill（通常是 `RA:analysis-plan` 或 `RA:report`）。
