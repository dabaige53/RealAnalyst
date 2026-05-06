# Metadata Audit

`metadata/audit/` 保存 metadata YAML 维护日志、ref 关联记录和变更报告。这里是审计层，不是分析语义层；`metadata context` 不应把这里的内容当作业务定义真源。

每次修改 `metadata/dictionaries/`、`metadata/mappings/` 或 `metadata/datasets/` 后，都应记录一次变更：

```bash
python3 skills/metadata/scripts/metadata.py record-change --summary "补充字段定义和证据" --path metadata/datasets/demo.retail.orders.yaml --dataset-id demo.retail.orders
```

默认生成：

```text
metadata/audit/metadata_changes.jsonl
metadata/audit/metadata_relations.jsonl
metadata/audit/metadata_change_report.md
```

当 dataset 字段或指标使用 `business_definition.ref` 指向 dictionary、mapping 或 refine 证据链时，可以记录一条关联：

```bash
python3 skills/metadata/scripts/metadata.py record-relation \
  --ref juneyao.metrics.ask \
  --dataset-id <dataset_id> \
  --section metrics \
  --name ask \
  --source-type dictionary \
  --target metadata/dictionaries/metrics.yaml \
  --evidence metadata/sources/refine/<refine_id>/evidence_manifest.json
```

关联记录只用于追溯和维护，不复制回 `metadata/datasets/*.yaml`。

如果修改来自 `RA:metadata-refine`，记录对应证据：

```bash
cp metadata/datasets/<dataset>.yaml /tmp/<dataset>.before.yaml

python3 skills/metadata/scripts/metadata.py record-change \
  --summary "基于 refine 材料修正字段定义" \
  --path metadata/datasets/<dataset>.yaml \
  --before /tmp/<dataset>.before.yaml \
  --dataset-id <dataset_id> \
  --refine-id <refine_id> \
  --evidence metadata/sources/refine/<refine_id>/evidence_manifest.json
```

这会额外生成：

```text
metadata/audit/refine-diffs/<refine_id>-<timestamp>.md
```

这份报告用于说明基于 refine 材料修改 YAML 后，到底改了哪些行。
