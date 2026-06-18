# Slice 5: data-export / data-profile artifact 登记

## Goal

让取数和画像产物进入 manifest，但默认标记为内部材料，不再暴露给用户。

## Why

raw data 和 profile 是复核证据，不是默认用户交付物。它们必须能被 report/analysis 读取，但不能进入普通回复和报告清单。

## Scope

- data-export 登记 raw export、export summary、可能的 user attachment。
- data-profile 登记 profile manifest/profile json 为 `derived_internal`。
- profile 结果只给 `user_surface` 提供业务化质量摘要。
- 修正或替换当前 Tableau-only 的 `manifest.schema.json`。
- 读取方优先从 manifest 定位 profile/export artifact。

## Non-goals

- 不改变导出数据内容。
- 不迁移旧 data/profile 目录。

## Acceptance Criteria

- [x] 原始导出默认 `internal_only=true`。
- [x] profile 文件默认 `internal_only=true`。
- [x] 用户回复不出现 `profile/manifest.json`。
- [x] 用户附件必须显式登记，不能靠文件名推断。
- [x] 通用 profile manifest schema 与实际输出一致。

## Dependencies

- Slice 1

## Validation

- `python3 -m py_compile scripts/update_artifact_index.py skills/data-profile/scripts/profiling_with_meta.py skills/data-export/scripts/duckdb/duckdb_export_with_meta.py skills/data-export/scripts/sql/export_with_meta.py skills/data-export/scripts/tableau/tableau_export_with_meta.py`
- `python3 -m pytest -q tests/test_export_profile_manifest_registration.py tests/test_job_manifest.py tests/test_analysis_run_manifest_integration.py tests/test_report_manifest_deliverables.py tests/test_report_verify_user_surface.py` （15 passed）
- `python3 -m pytest -q tests/test_metadata_product_fixes.py::MetadataProductFixTests::test_analysis_init_job_supports_installed_skill_workspace tests/test_metadata_product_fixes.py::MetadataProductFixTests::test_mysql_clickhouse_export_help_and_audit_sql_summary` （2 passed）
- `python3 -m json.tool schemas/manifest.schema.json`
- data-export artifact registration smoke covered by `tests/test_export_profile_manifest_registration.py`
- data-profile artifact registration smoke covered by `tests/test_export_profile_manifest_registration.py`
- manifest schema compatibility test covered by `tests/test_export_profile_manifest_registration.py`
