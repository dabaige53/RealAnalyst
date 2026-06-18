# Slice 9: delivered job finalize 与内部归档

## Goal

完成后的 job 可以收缩目录噪音：用户入口保留 manifest 和 deliverables，内部证据可归档或压缩，但必须先审核确认。

## Why

用户要的是干净项目目录，但 RealAnalyst 不能牺牲可复核性。归档必须 review-first。

## Scope

- 定义 job 状态：active、delivered、archived、failed。
- 根据 manifest 计算归档候选。
- 生成 archive review pack。
- 用户确认后移动或压缩 internal 文件。
- manifest 保留 hash、行数、字段、来源和恢复索引。

## Non-goals

- 不归档 active job。
- 不默认删除证据。
- 不绕过用户确认。

## Acceptance Criteria

- [x] active job 不会被归档。
- [x] delivered job 可生成归档候选。
- [x] 未确认前不移动、不删除。
- [x] 归档后 manifest 仍能定位证据或恢复包。

## Dependencies

- Slice 1
- Slice 3
- Slice 8

## Validation

- `python3 -m py_compile scripts/finalize_job_archive.py runtime/job_manifest.py`
- `python3 -m pytest -q tests/test_finalize_job_archive.py tests/test_job_manifest.py` （6 passed）
- archive dry-run test covered by `tests/test_finalize_job_archive.py`
- confirmation-gated apply test covered by `tests/test_finalize_job_archive.py`
- recovery index test covered by `tests/test_finalize_job_archive.py`
