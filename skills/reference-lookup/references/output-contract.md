# Output Contract

`query_config.py` 的返回契约分为两类。

## 列表类查询

适用于 `--template`、`--glossary`、`--metric`、`--dimension`。

- 统一字段：`query` / `type` / `matches` / `count`
- `count` 必须等于 `len(matches)`
- `matches` 允许为空列表，但字段不能缺失

示例：

```json
{
  "query": "周报",
  "type": "template",
  "matches": [
    {
      "id": "weekly_sales",
      "name": "销售周报",
      "trigger_keywords": ["周报", "weekly"],
      "description": "按周输出销售概览"
    }
  ],
  "count": 1
}
```

## 框架查询

适用于 `--framework`，使用单对象契约而不是 `matches/count`。

命中时：

- `query`
- `type`
- `found=True`
- `framework`

```json
{
  "query": "mece",
  "type": "framework",
  "found": true,
  "framework": {
    "id": "mece_issue_tree",
    "name": "MECE 问题树",
    "name_en": "MECE Issue Tree",
    "aliases": ["mece", "issue_tree"],
    "description": "把一个业务问题拆成互斥且穷尽的子问题。",
    "logic_path": ["定义主问题", "拆一级问题域", "校验互斥穷尽"],
    "goal_template": {
      "fixed": ["明确分析范围、数据口径和主问题"]
    },
    "dimension_type_hints": {
      "category": "优先作为一级或二级问题分支"
    },
    "evidence_requirements": ["主问题对应的核心指标"],
    "recommended_templates": [
      {"template": "summary_structured", "when": "需要正式专题报告"}
    ]
  }
}
```

未命中时：

- `query`
- `type`
- `found=False`
- `available_frameworks`

```json
{
  "query": "unknown",
  "type": "framework",
  "found": false,
  "available_frameworks": [
    {
      "id": "mece_issue_tree",
      "name": "MECE 问题树",
      "aliases": ["mece", "issue_tree"],
      "scenarios": []
    }
  ]
}
```

## Out Of Scope

datasource 查询不在此处定义返回 schema；本文件只覆盖 `template` / `glossary` / `metric` / `framework` / `dimension` 五类契约。
