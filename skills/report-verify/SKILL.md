---
name: "RA:report-verify"
description: |
  Use when: (1) Validating a report before delivery, (2) Need a machine-readable verification.json
  summary, (3) Need to confirm evidence chain, rankings, trends, appendix, and output-file-list
  compliance, (4) Need to decide whether a report can pass the final gate. Triggers: verify, 验证报告,
  交付前校验, verification.json, 一致性校验, 最终门禁.
---

# Verify Skill

交付前质量门禁。验证报告中的声明、口径和必备章节是否与数据、分析结果和输出契约一致。

## 用法

```bash
python3 {baseDir}/skills/report-verify/scripts/verify.py --help
python3 {baseDir}/skills/report-verify/scripts/verify.py <data_csv> <analysis_json> <report_md> <output_dir>
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `data_csv` | 用于校验报告结论的正式分析数据 CSV（优先使用宽表或 plan/export_summary/duckdb_export_summary 指定的产物） |
| `analysis_json` | 分析结果文件 |
| `report_md` | 待验证的报告 |
| `output_dir` | 输出目录，脚本会写入 `verification.json` |

## 依赖

- Python 标准库
- `pandas`

## 标准输出

脚本会向 stdout 输出机器可解析 JSON：

```json
{
  "success": true,
  "status": "warning",
  "verification_path": "jobs/job_001/verification.json",
  "passed": 12,
  "failed": 0,
  "warnings": 2
}
```

- `success = false` 仅在 `status = failed` 时出现。
- 自动化流程应以 stdout JSON 和 `verification.json` 为准，不要依赖日志文本。

## verification.json 结构

```json
{
  "job_id": "job_001",
  "verified_at": "2026-03-06T10:00:00",
  "status": "warning",
  "checks": [
    {
      "check_id": "ev_finding_001",
      "check_type": "evidence_completeness",
      "target": "关键结论标题",
      "status": "warning",
      "details": {
        "has_calculation": false,
        "has_row_indices": true
      },
      "message": "缺少 calculation 字段"
    }
  ],
  "summary": {
    "total_checks": 18,
    "passed": 16,
    "failed": 0,
    "warnings": 2
  },
  "check_categories": {
    "evidence_completeness": 4,
    "ranking_consistency": 2,
    "trend_consistency": 1,
    "numeric_traceability": 3,
    "confidence_threshold": 4,
    "metric_definition_appendix": 1,
    "metric_term_consistency": 1,
    "data_source_section_position": 1,
    "data_source_display_name": 1,
    "output_file_list_section": 1
  }
}
```

`checks[*]` 的核心字段：

- `check_id`：单项检查唯一标识
- `check_type`：检查类别
- `target`：被检查对象
- `status`：`passed` / `warning` / `failed`
- `details`：结构化上下文
- `message`：仅在 warning / failed 时出现

## 验证状态定义

| 状态 | 条件 | 说明 |
| --- | --- | --- |
| `passed` | failed = 0, warnings = 0 | 报告可通过门禁 |
| `warning` | failed = 0, warnings > 0 | 报告需人工复核 |
| `failed` | failed > 0 | 报告存在硬性问题，禁止交付 |

未标注为推断口径的 `needs_review=true` 指标不得作为确定口径通过验证。

## 当前检查项

1. `evidence_completeness`：每条 finding 是否具备 calculation / row_indices 等证据链。
2. `ranking_consistency`：排名结论是否与统计结果一致。
3. `trend_consistency`：增长、下降、改善、恶化等方向是否一致。
4. `numeric_traceability`：报告中的关键数字是否可追溯到分析结果或原始数据。
5. `confidence_threshold`：低置信度 finding 是否被错误地当成确定结论。
6. `metric_definition_appendix`：是否包含 `## 口径说明（本次新增/临时）`。
7. `metric_term_consistency`：是否把子集指标静默写成总量指标。
8. `data_source_section_position`：`## 数据来源` 是否位于报告前部。
9. `data_source_display_name`：数据源展示是否保持中文业务名。
10. `output_file_list_section`：是否包含 `## 输出文件清单`。

## 示例

```bash
python3 {baseDir}/skills/report-verify/scripts/verify.py \
  {baseDir}/jobs/job_001/data/交叉_销售_2025Q1.csv \
  {baseDir}/jobs/job_001/analysis.json \
  {baseDir}/jobs/job_001/报告_上海区域代理人销售分析_2025Q4.md \
  {baseDir}/jobs/job_001
```

## Completion Summary

验证完成后，向用户汇报：

1. `verification.json` 已生成，总检查数 / 通过 / 失败 / 警告。
2. 列出失败项和警告项的摘要。
3. 如果全部通过：下一步建议是交付报告给用户。
4. 如果有失败项：下一步建议是回到 `/skill RA:report` 修正对应问题后重新验证。
