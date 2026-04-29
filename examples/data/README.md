# Demo Data

这里保存脱敏的最小 demo 数据，用于本地 smoke test 和新用户试跑。

| 文件 | 用途 |
| --- | --- |
| `retail_orders.csv` | 订单粒度的零售 demo 数据，用于 metadata 和 profiling 示例。 |
| `retail_forecast.csv` | 预测 demo 数据，用于 DuckDB 聚合导出测试。 |

生成 `data-export` smoke test 使用的本地 DuckDB：

```bash
python3 examples/build_demo_duckdb.py
python3 runtime/duckdb/register_duckdb_sources.py
python3 skills/data-export/scripts/duckdb/run_tests.py
```

生成的 `examples/data/demo_retail.duckdb` 已被 `.gitignore` 忽略，可以随时重建。
