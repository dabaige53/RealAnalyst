# Output Schema

推荐入口 `run.py` 会自动解析正式 CSV，并调用 `profile.py` 在 `<output_dir>/profile/` 下写出两个正式产物。两个入口都会在 CLI stdout 返回最终 JSON 结果。

## CLI Return

### `run.py`

核心字段与 `profile.py` 一致，并补充输入解析信息：

```json
{
  "success": true,
  "manifest_path": "jobs/job_001/profile/manifest.json",
  "profile_path": "jobs/job_001/profile/profile.json",
  "row_count": 50000,
  "column_count": 12,
  "quality_score": 0.95,
  "signals": {
    "has_datetime": true,
    "metric_count": 6,
    "dimension_count": 4
  },
  "data_csv": "jobs/job_001/data/交叉_sales.ai__.csv",
  "output_dir": "jobs/job_001",
  "resolved_from": "export_summary"
}
```

### `profile.py`

```json
{
  "success": true,
  "manifest_path": "jobs/job_001/profile/manifest.json",
  "profile_path": "jobs/job_001/profile/profile.json",
  "row_count": 50000,
  "column_count": 12,
  "quality_score": 0.95,
  "signals": {
    "has_datetime": true,
    "metric_count": 6,
    "dimension_count": 4
  }
}
```

## `profile/manifest.json`

关键字段：

- `id`
- `source_key`
- `view_luid`
- `display_name`
- `source_ref`
- `row_count`
- `column_count`
- `schema.columns[]`
- `profile_summary`
- `lineage`

```json
{
  "id": "ds_job_001",
  "source_ref": "jobs/job_001/data.csv",
  "row_count": 50000,
  "column_count": 12,
  "schema": {
    "columns": [
      {
        "name": "产品线",
        "physical_type": "string",
        "role": "dimension",
        "semantic_type": "category"
      }
    ]
  },
  "profile_summary": {
    "quality_score": 0.95,
    "missing_values": {
      "客单价": 3
    }
  },
  "lineage": {
    "source": "profiling_skill",
    "transforms": []
  }
}
```

## `profile/profile.json`

关键字段：

- `job_id`
- `profiled_at`
- `data_file`
- `data_summary`
- `schema`
- `signals`
- `quality`
- `statistics`

```json
{
  "job_id": "job_001",
  "data_file": "jobs/job_001/data.csv",
  "data_summary": {
    "rows": 50000,
    "columns": 12,
    "memory_usage_mb": 8.42
  },
  "signals": {
    "has_datetime": true,
    "metric_count": 6,
    "dimension_count": 4
  },
  "quality": {
    "score": 0.95,
    "issues": [],
    "missing_stats": {
      "客单价": {
        "count": 3,
        "percentage": 0.01
      }
    }
  },
  "statistics": {
    "numeric": {},
    "categorical": {}
  }
}
```
