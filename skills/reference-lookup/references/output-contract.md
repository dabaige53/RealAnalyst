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
      "id": "mece",
      "name": "MECE",
      "scenarios": ["结构分析"]
    }
  ]
}
```

## Out Of Scope

datasource 查询不在此处定义返回 schema；本文件只覆盖 `template` / `glossary` / `metric` / `framework` / `dimension` 五类契约。
