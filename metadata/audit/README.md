# Metadata Audit

`metadata/audit/` 保存 metadata YAML 维护日志和变更报告。

每次修改 `metadata/dictionaries/`、`metadata/mappings/` 或 `metadata/datasets/` 后，都应记录一次变更：

```bash
python3 skills/metadata/scripts/metadata.py record-change --summary "补充字段定义和证据" --path metadata/datasets/demo.retail.orders.yaml --dataset-id demo.retail.orders
```

默认生成：

```text
metadata/audit/metadata_changes.jsonl
metadata/audit/metadata_change_report.md
```

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
