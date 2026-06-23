# Slice 8: legacy job manifest dry-run 迁移

## Goal

为旧 job 生成候选 manifest 和迁移报告，但不移动、不删除文件。

## Why

历史 job 很多，不能一刀切迁移。先 dry-run 建索引，才能安全判断哪些是用户交付物、哪些是内部证据、哪些不确定。

## Scope

- 扫描旧 job 目录。
- 推断 artifact role。
- 生成 candidate `job_manifest.json` 或 dry-run payload。
- 生成 review report。
- 不确定文件标记为 `unknown_legacy`。
- 不移动、不压缩、不删除。

## Non-goals

- 不批量清理历史 job。
- 不自动归档。

## Acceptance Criteria

- [x] dry-run 不改变旧 job 文件。
- [x] 能输出候选 manifest。
- [x] 不确定项单列。
- [x] 输出可作为 job-maintenance review 输入。

## Dependencies

- Slice 1

## Validation

- `python3 -m py_compile scripts/legacy_job_manifest_migration.py runtime/job_manifest.py`
- `python3 -m pytest -q tests/test_legacy_job_manifest_migration.py tests/test_job_manifest.py` （4 passed）
- fixture old job scan test covered by `tests/test_legacy_job_manifest_migration.py`
- no-write dry-run assertion covered by `tests/test_legacy_job_manifest_migration.py`
