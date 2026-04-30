# RA:metadata-refine

把分析 job、用户反馈、profile 和真实数据探查结果整理成元数据修正参考材料。

它不直接修改正式 YAML，也不发布 `runtime/registry.db`。完成后的材料归档到 `metadata/sources/refine/{refine_id}/`，再由 `RA:metadata` 基于这些证据维护 dictionaries / mappings / datasets。

## 典型流程

```bash
python3 skills/metadata-refine/scripts/collect_feedback.py --session-id <SESSION_ID> --list
python3 skills/metadata-refine/scripts/probe_data.py --session-id <SESSION_ID> --data-csv jobs/<SESSION_ID>/data/<file>.csv --dataset-id <dataset_id>
python3 skills/metadata-refine/scripts/build_reference_pack.py --session-id <SESSION_ID> --dataset-id <dataset_id>
python3 skills/metadata-refine/scripts/archive_reference_pack.py --refine-id <refine_id> --session-id <SESSION_ID>
```

## 产物

临时目录：

```text
runtime/metadata-refine/{refine_id}/
```

归档目录：

```text
metadata/sources/refine/{refine_id}/
```

关键文件：

| 文件 | 作用 |
| --- | --- |
| `refine_brief.md` | 本次修正材料摘要 |
| `feedback_summary.md` | 用户反馈和分析发现汇总 |
| `data_probe_summary.md` | 真实数据轻量探查摘要 |
| `metadata_update_reference.md` | 给 `RA:metadata` 的修正参考 |
| `evidence_manifest.json` | 来源、输入、归档位置和证据链 |
