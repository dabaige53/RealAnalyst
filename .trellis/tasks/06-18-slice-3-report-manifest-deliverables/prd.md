# Slice 3: report 交付物改为 manifest 驱动

## Goal

报告生成后显式登记用户可见交付物，输出文件清单从 manifest 读取，不再扫描 job 根目录。

## Why

现在报告清单容易把过程 CSV、系统 JSON、profile、source context 混进用户视野。用户只应看到报告和明确交付附件。

## Scope

- report 生成后登记 `user_deliverable`。
- 业务附件登记为 `user_attachment`。
- 报告末尾“输出文件清单”由 manifest 的 user-visible artifact 生成。
- 更新 `skills/report/SKILL.md` 和 `skills/report/references/output-contract.md`。
- manifest 缺失时可 fallback 到旧逻辑，但必须标记 legacy warning。

## Non-goals

- 不改变报告分析内容。
- 不删除旧清单逻辑，先保留 fallback。

## Acceptance Criteria

- [x] 报告 artifact 角色为 `user_deliverable`。
- [x] 只有显式 `user_attachment` 进入用户清单。
- [x] 原始 data、profile、verification 不进入用户清单。
- [x] 报告正文默认不展示内部路径。

## Dependencies

- Slice 1
- Slice 2

## Validation

- `python3 -m py_compile skills/report/scripts/append_report_update.py runtime/job_manifest.py`
- `python3 -m pytest -q tests/test_job_manifest.py tests/test_analysis_run_manifest_integration.py tests/test_report_manifest_deliverables.py` （8 passed）
- report output contract smoke covered by `tests/test_report_manifest_deliverables.py`
- manifest-visible artifact test covered by `tests/test_report_manifest_deliverables.py`
- legacy fallback test covered by `tests/test_report_manifest_deliverables.py`
