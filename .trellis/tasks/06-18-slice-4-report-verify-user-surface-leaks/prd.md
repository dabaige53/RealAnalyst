# Slice 4: report-verify 用户态泄露门禁

## Goal

报告中出现内部路径、source key、脚本名、schema 字段或工程术语时，默认无法通过交付门禁。

## Why

只靠写作规则无法约束 agent。需要机器检查防止内部细节进入用户报告。

## Scope

- 增加内部路径泄露检查。
- 增加内部术语/source key 泄露检查。
- 支持技术详情例外，但必须有 manifest 标记或显式输入。
- 验证完成后更新 manifest 的 `user_surface.verification_status`。
- 修正 `verification.schema.json` 与真实 check types/check ids 的漂移。

## Non-goals

- 不做敏感信息 DLP 全覆盖。
- 不阻止开发/排障模式输出技术细节。

## Acceptance Criteria

- [x] 普通报告出现内部路径时验证失败。
- [x] 普通报告出现系统 source key 时验证失败或升级为失败。
- [x] 用户要求技术详情时可豁免指定段落。
- [x] `verification.json` schema 与实际输出一致。
- [x] manifest 能读取最终验证状态。

## Dependencies

- Slice 3

## Validation

- `python3 -m py_compile runtime/job_manifest.py skills/analysis-run/scripts/init_or_resume_job.py skills/analysis-run/scripts/render_user_reply.py skills/report/scripts/append_report_update.py skills/report-verify/scripts/verify.py`
- `python3 -m pytest -q tests/test_job_manifest.py tests/test_analysis_run_manifest_integration.py tests/test_report_manifest_deliverables.py tests/test_report_verify_user_surface.py` （12 passed）
- `python3 -m json.tool schemas/verification.schema.json`
- report-verify leak positive/negative tests covered by `tests/test_report_verify_user_surface.py`
- verification schema compatibility test covered by `tests/test_report_verify_user_surface.py`
