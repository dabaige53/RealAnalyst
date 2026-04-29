# Metadata Dictionaries

维护跨数据源复用的公共语义定义。

建议文件：

- `metrics.yaml`：公共指标字典
- `dimensions.yaml`：公共维度和维度字段字典
- `glossary.yaml`：公共业务术语、航司、机场、枚举词表

这些文件会进入 `metadata index`，但不能作为 `metadata context --dataset-id` 的目标。
