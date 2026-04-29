# Contributing

RealAnalyst 是 metadata-first 的 Codex 数据分析 skill suite。

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

## Validation

发布公开变更前，至少运行：

```bash
python3 -m json.tool .codex-plugin/plugin.json
python3 skills/metadata/scripts/metadata.py validate
```

公开仓库不包含 `tests/`。维护者可以在本地保留私有测试，但不要把它们放进发布树。

## Contribution Rules

- `metadata` 是用户维护元数据的统一入口。
- 不要重新引入独立的 `tableau-sync`、`duckdb-sync`、`metadata-search` 或 `osi-export` 用户入口。
- Tableau 和 DuckDB 的发现/同步逻辑放在 `skills/metadata/adapters/`。
- 不要提交 `.env`、本地数据库、任务输出或 Tableau/DuckDB 凭据。
- 如果字段或指标定义是推断出来的，必须写明证据、置信度和 review 状态。
