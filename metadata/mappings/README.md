# Metadata Mappings

维护 source 字段到标准语义的映射和口径覆盖。

每个文件建议对应一个 source：

```text
tableau.sales.agent.mapping.yaml
duckdb.ho.view_dwd_zy_flight_results.mapping.yaml
```

这些文件会生成 `metadata/index/mappings.jsonl`，供需求理解和 source 选择阶段检索。
