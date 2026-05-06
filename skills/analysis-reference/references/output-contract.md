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
    "id": "mece",
    "name": "MECE",
    "name_en": "MECE",
    "description": "Mutually exclusive, collectively exhaustive",
    "applicable_scenarios": ["结构分析"],
    "logic_path": ["总量", "结构", "归因"],
    "goal_template": {},
    "dimension_type_hints": {}
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
      "id": "monitoring",
      "name": "经营监控",
      "scenarios": ["trend", "alert", "routine report"]
    }
  ]
}
```

## Out Of Scope

- metric / field / term 查询：使用 `RA:metadata-search`
- datasource 查询：使用 `query_registry.py`
