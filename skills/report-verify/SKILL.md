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

验证通过不等于已经交付。报告进入 Slack、邮件或 Drive 前，必须再生成 `delivery_manifest.json`，并按清单上传 Markdown 报告和用户态 CSV 附件。外部上传动作由宿主 agent / gateway 执行；本 skill 只生成可检查清单和门禁状态。

## 用法

```bash
python3 {baseDir}/skills/report-verify/scripts/verify.py --help
python3 {baseDir}/skills/report-verify/scripts/verify.py <data_csv> <analysis_json> <report_md> <output_dir>
python3 {baseDir}/skills/report-verify/scripts/build_delivery_manifest.py --session-id <SESSION_ID> --platform slack
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `data_csv` | 用于校验报告结论的正式分析数据 CSV（优先使用宽表或 plan/export_summary/duckdb_export_summary 指定的产物） |
| `analysis_json` | 分析结果文件 |
| `report_md` | 待验证的报告 |
| `output_dir` | 输出目录，脚本会写入 `verification.json` |

`build_delivery_manifest.py` 参数：

| 参数 | 说明 |
| --- | --- |
| `--session-id` | job id；也可通过环境变量 `SESSION_ID` 提供 |
| `--platform` | 交付平台名称，例如 `slack` / `email` / `drive` |
| `--upload-receipt-json` | 可选；外部上传器返回的 JSON receipt，含 `success=true` 或 `ok=true` 时状态为 `upload_receipt_recorded` |

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

## 最终交付门禁

验证结束后必须执行：

```bash
python3 {baseDir}/skills/report-verify/scripts/build_delivery_manifest.py --session-id <SESSION_ID> --platform slack
```

`delivery_manifest.json` 的状态含义：

| 状态 | 条件 | 处理 |
| --- | --- | --- |
| `blocked` | 报告或必要附件缺失 | 回到对应 owner skill 修复，不回复“已完成” |
| `ready_for_upload` | 文件齐全，但没有外部上传 receipt | 宿主 agent 必须上传报告和附件；不能只发摘要 |
| `upload_receipt_recorded` | 文件齐全且已记录外部上传 receipt | 可以给用户最终简短回复；真实上传动作仍由宿主 agent / Slack / email / Drive gateway 完成 |

`delivery_manifest` 只证明“应交付文件齐全 / 已有上传 receipt”，不执行上传；真实交付仍依赖宿主 agent / Slack / email / Drive gateway 按 manifest 做动作。

面向用户的最终回复只保留业务结论、文件名、口径边界和下一步建议。默认不要暴露 job 路径、registry、metadata feedback、脚本名或内部错误；除非用户正在排障并明确要求。

## 示例

```bash
python3 {baseDir}/skills/report-verify/scripts/verify.py \
  {baseDir}/jobs/job_001/data/交叉_销售_2025Q1.csv \
  {baseDir}/jobs/job_001/analysis.json \
  {baseDir}/jobs/job_001/报告_上海区域代理人销售分析_2025Q4.md \
  {baseDir}/jobs/job_001
```

## Completion Summary

验证完成后，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已生成 `verification.json`。
- 已生成 `delivery_manifest.json`，状态：<blocked / ready_for_upload / upload_receipt_recorded>
- 检查结果：<总检查数 / 通过 / 失败 / 警告>
- 失败项和警告项摘要：<按实际列出>

下一步建议：
- 最推荐下一步：按 delivery manifest 上传报告和用户态附件（ready_for_upload 时）/ 确认上传 receipt 后给用户最终回复（upload_receipt_recorded 时）
- 可选下一步：/skill RA:report ...（报告内容需修正时）
- 可选下一步：/skill RA:metadata-refine ...（验证暴露口径缺口、review gap 或 metadata 问题时）

边界提醒：
- 本 skill 只做交付前门禁检查，没有修改报告、数据或正式 metadata。
- 未通过项需要回到对应 owner skill 修正后重新验证。
```
