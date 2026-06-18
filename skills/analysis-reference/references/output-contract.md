# Output Contract

`query_config.py` 的返回契约分为两类。

## 模板查询

适用于 `--template`。

- 统一字段：`query` / `type` / `matches` / `count`
- `count` 必须等于 `len(matches)`
- `matches` 允许为空列表，但字段不能缺失

示例：

```json
{
  "query": "月报",
  "type": "template",
  "matches": [
    {
      "matched_via": "template_reference",
      "source": "skills/report/references/template-system-v2.md",
      "line": "| monthly_analysis | 月度经营分析 | ..."
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
    "best_for": ["整体情况不清楚"],
    "not_suitable_for": ["已经明确只需要解释单个指标变化原因"],
    "analysis_modes": ["overview", "exploration"],
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
    ],
    "failure_modes": ["分支互相重叠导致重复归因"],
    "source_refs": ["issue_tree", "mece_principle"]
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

- metric / field / term 查询：使用 `RA:metadata-search`
- datasource 查询：使用 `query_registry.py`
