# brainstorm: optimize RealAnalyst installed skill runtime paths

## Goal

Fix RealAnalyst installed-mode analysis flow so project-local installs under `.agents/skills` behave like source checkouts under `skills`. The user saw analysis-run degrade into manual workaround because script path resolution and workspace discovery assumed source layout.

## What I Already Know

* The failing target workspace used project-local skills at `.agents/skills`.
* `scripts/py` currently only forwards to Python and does not map `skills/...` to `.agents/skills/...`.
* `analysis-run/scripts/init_or_resume_job.py` only recognizes a workspace with `runtime/` and `skills/`, so it fails from installed skill paths.
* Several analysis flow wrapper scripts use the same source-only workspace root check.
* `getting-started/scripts/doctor.py` reports missing `duckdb`, but the output should include a concrete remediation command for installed workspaces.

## Requirements

* `./scripts/py skills/<skill>/...` must work in project-local installed workspaces where only `.agents/skills/<skill>/...` exists.
* Continuous analysis scripts must discover workspace root from either `skills/` or `.agents/skills/`.
* Doctor output must keep read-only behavior and return actionable dependency remediation for DuckDB-backed analysis/export.
* Changes must stay targeted and not initialize business folders during install.

## Acceptance Criteria

* [x] Unit tests cover `scripts/py` path mapping in a temporary installed-mode workspace.
* [x] Unit tests cover `init_or_resume_job.py` running from `.agents/skills`.
* [x] Doctor JSON includes a concrete `remediation` command when DuckDB is missing for analysis/export.
* [x] Existing product fix tests pass.

## Out of Scope

* Changing business metadata schema.
* Running a real DuckDB export.
* Creating demo `metadata/`, `jobs/`, `logs`, or `runtime/registry.db` during install.

## Technical Notes

* Main files: `scripts/py`, `skills/analysis-run/scripts/init_or_resume_job.py`, `skills/getting-started/scripts/doctor.py`.
* Related wrappers: `skills/data-export/scripts/duckdb/duckdb_export_with_meta.py`, `skills/data-profile/scripts/profiling_with_meta.py`, `skills/report/scripts/append_report_update.py`.
