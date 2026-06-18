# Slice 6: analysis-plan 契约与 schema 漂移修复

## Goal

修复 plan 文档、schema、framework 查询、模板锁定之间的不一致，让 plan 决策可以被 manifest 和 report 稳定消费。

## Why

当前 `analysis_plan.schema.json` 描述旧 JSON operator plan，但文档声称它约束 Markdown `analysis_plan.md`。这会误导 agent 和测试。

## Scope

- manifest 登记 plan artifact。
- manifest 记录 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template`。
- 旧 `analysis_plan.schema.json` 改名、降级说明或替换为真实契约。
- 新增 Markdown plan contract 或 plan decision schema。
- 确认 analysis-reference framework 查询和旧别名可命中。

## Non-goals

- 不重写整个 planning 方法论。
- 不改变报告模板体系的 6 个核心模板方向。

## Acceptance Criteria

- [x] 文档不再声称 Markdown plan 由旧 JSON operator schema 约束。
- [x] plan 三项模板锁定结果能从 manifest 读取。
- [x] framework 查询返回完整配置。
- [x] report 阶段不得重新选模板。

## Dependencies

- Slice 1
- framework lookup fix

## Validation

- `python3 -m py_compile runtime/job_manifest.py skills/analysis-plan/scripts/validate_plan.py skills/analysis-reference/scripts/query_config.py skills/reference-lookup/scripts/query_config.py`
- `python3 -m pytest -q tests/test_analysis_reference_frameworks.py tests/test_analysis_plan_contract.py tests/test_job_manifest.py` （8 passed, 9 subtests passed）
- `python3 -m pytest -q tests/test_job_manifest.py tests/test_analysis_run_manifest_integration.py tests/test_report_manifest_deliverables.py tests/test_report_verify_user_surface.py tests/test_export_profile_manifest_registration.py tests/test_analysis_reference_frameworks.py tests/test_analysis_plan_contract.py` （20 passed, 9 subtests passed）
- `python3 -m json.tool schemas/analysis_plan.schema.json`
- `python3 -m json.tool schemas/analysis_plan_decision.schema.json`
- `python3 -m json.tool schemas/job_manifest.schema.json`
- framework lookup tests covered by `tests/test_analysis_reference_frameworks.py`
- plan contract tests covered by `tests/test_analysis_plan_contract.py`
- docs/schema consistency smoke covered by JSON schema checks and schema docs updates
