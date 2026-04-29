# Data Profile Skill

为正式 CSV 生成数据画像，检查字段、缺失、异常、语义类型、行列规模和分布。

---

## 什么时候用？

- 取数完成后
- 正式分析前
- 需要确认数据质量
- 同一 job 内补数后需要重新画像

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 正式 CSV<br/>export_summary.json 或 duckdb_export_summary.json<br/>SESSION_ID |
| 输出 | profile/manifest.json<br/>profile/profile.json<br/>artifact_index 更新 |
| 下一步 | `RA:report` |

---

## 流程图

```mermaid
flowchart LR
    CSV[正式 CSV] --> Profile[run.py] --> Manifest[manifest.json] --> Quality[profile.json] --> Report[report 使用画像]
```

---

## 快速示例

```bash
python3 skills/data-profile/scripts/run.py --data-csv jobs/$SESSION_ID/data/<正式CSV文件名> --output-dir jobs/$SESSION_ID
```

---

## 用户会得到什么？

- 数据规模、字段类型、缺失、异常和分布摘要。
- `profile/manifest.json` 和 `profile/profile.json`。
- 对报告写作有用的质量提醒。
- 是否需要重新取数或补充字段的判断依据。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `RA:analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 检查 CSV 是否是正式导出文件，而不是临时样本 |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
