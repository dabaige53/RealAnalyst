# Evidence Manifest Schema

`evidence_manifest.json` 是 `RA:metadata-refine` 生成的参考包的核心索引文件，归档后位于 `metadata/sources/refine/{refine_id}/`。

## 字段定义

```json
{
  "refine_id": "refine_20260430_001",
  "created_at": "2026-04-30T10:00:00",
  "job_id": "job_abc123",
  "dataset_id": "demo.retail.orders",
  "inputs": {
    "feedback_file": "runtime/metadata-refine/{refine_id}/feedback_summary.md",
    "data_csv": "jobs/{job_id}/data/交叉_销售_2025Q1.csv",
    "profile_json": "jobs/{job_id}/profile/profile.json"
  },
  "outputs": {
    "refine_brief": "refine_brief.md",
    "refine_followup": "refine_followup.md",
    "feedback_summary": "feedback_summary.md",
    "data_probe_summary": "data_probe_summary.md",
    "metadata_update_reference": "metadata_update_reference.md"
  },
  "archived_at": "metadata/sources/refine/{refine_id}/",
  "issues": [
    {
      "issue_type": "field_definition_unclear",
      "field": "discount_rate",
      "summary": "字段含义不明确，需要业务确认"
    }
  ]
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `refine_id` | ✅ | 本次 refine 的唯一 ID，格式 `refine_{date}_{seq}` |
| `created_at` | ✅ | ISO 8601 时间戳 |
| `job_id` | 有则填 | 来源 analysis job 的 SESSION_ID |
| `dataset_id` | ✅ | 对应的 metadata dataset ID |
| `inputs` | ✅ | 输入文件路径（feedback / CSV / profile） |
| `outputs` | ✅ | 生成的参考文件列表 |
| `archived_at` | 归档后填 | 归档后的目录路径 |
| `issues[]` | ✅ | 问题清单，每项包含 issue_type / field / summary |

## issue_type 枚举

| 值 | 说明 |
|---|---|
| `field_definition_unclear` | 字段业务含义不明确 |
| `metric_formula_incorrect` | 指标公式有误或不完整 |
| `evidence_missing` | 缺少来源证据 |
| `review_required` | 需要业务确认 |
| `value_range_anomaly` | 字段值域与定义不符 |

## 归档路径约定

- 临时工作区：`runtime/metadata-refine/{refine_id}/`
- 正式归档区：`metadata/sources/refine/{refine_id}/`
- `RA:metadata` 只引用归档路径，不引用 runtime 临时路径
