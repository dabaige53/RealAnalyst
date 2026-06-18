# audit fatal skill contract drift

## Goal

Audit RealAnalyst for fatal contract drift where skill documentation, CLI behavior, templates, schemas, validation rules, or workflow promises diverge enough to mislead agents or break analysis workflows.

## What I Already Know

- The current sample issue is `RA:analysis-reference` framework lookup: docs say `query_config.py --framework <name>` returns framework configuration, but the previous implementation returned only misses.
- Report templates do exist under `skills/report/references/`; the sample issue is not missing report templates.
- Current dirty worktree includes edits to both `skills/analysis-reference/scripts/query_config.py` and `skills/reference-lookup/scripts/query_config.py`, plus pre-existing `.trellis/.template-hashes.json`.

## Scope

- Skill contracts in `skills/*/SKILL.md` and nearby `README.md` / `references/*.md`.
- Python CLI entrypoints under `skills/**/scripts/` and `runtime/**`.
- Validation or output-contract documents that promise fields, commands, or behavior.
- High-risk generated or compatibility duplicate paths such as `analysis-reference` and `reference-lookup`.
- Job output structure and user-facing communication contracts where internal paths, English IDs, script names, or project jargon leak into reports or chat replies.

## Out of Scope

- Full business metadata correctness review.
- Rewriting report content or analysis templates unless needed to document contract drift.
- Production data verification unless a CLI contract explicitly depends on live registry data.

## Fatal Error Definition

A finding is fatal when it can cause an agent or user to choose the wrong workflow, trust a command that cannot return the promised payload, skip a required source-of-truth step, or generate downstream artifacts with invalid contracts.

## Acceptance Criteria

- [x] Identify confirmed fatal contract drift issues with file paths and evidence.
- [x] Separate confirmed issues from lower-risk inconsistencies and false positives.
- [x] For each confirmed issue, state likely impact, minimal fix direction, and validation command.
- [x] Verify the already-modified framework lookup behavior before treating it as fixed.
- [x] Define a user-facing output boundary for both reports and assistant replies: users see business-readable outcomes, verification status, and deliverable names by default; internal file paths, script names, source keys, and English project terms appear only on request or in debug/engineering contexts.
- [x] Evaluate whether job folders can be compressed around a single durable job manifest/index while preserving raw data, evidence provenance, replayability, and failure recovery.
- [x] Do not overwrite unrelated dirty worktree changes.

## Technical Notes

- Start with grep/static checks for phrases like "returns complete config", "must include", "output contract", "schema", "query", and compare against script behavior.
- Prioritize executable claims over wording-only inconsistencies.

## Child Implementation Slices

The job output/user-surface redesign is split into child tasks so each implementation slice is independently verifiable:

| Order | Child task | Dependency | Purpose |
| --- | --- | --- | --- |
| 1 | `06-18-slice-1-job-manifest-ledger` | None | Minimal `job_manifest.json` schema and safe helper. |
| 2 | `06-18-slice-2-analysis-run-manifest-replies` | Slice 1 | `analysis-run` creates manifest and replies from user surface. |
| 3 | `06-18-slice-3-report-manifest-deliverables` | Slice 1, 2 | Report deliverables and output list become manifest-driven. |
| 4 | `06-18-slice-4-report-verify-user-surface-leaks` | Slice 3 | Verification fails reports that leak internal paths or source keys. |
| 5 | `06-18-slice-5-export-profile-artifact-registration` | Slice 1 | Export/profile artifacts are registered and hidden by default. |
| 6 | `06-18-slice-6-plan-schema-contract-repair` | Slice 1 + framework lookup fix | Plan/schema/framework contract drift is repaired. |
| 7 | `06-18-slice-7-project-reply-surface-policy` | Slice 2 | Project-level rule covers chat replies as well as reports. |
| 8 | `06-18-slice-8-legacy-job-manifest-migration` | Slice 1 | Old jobs can get dry-run candidate manifests. |
| 9 | `06-18-slice-9-delivered-job-finalize-archive` | Slice 1, 3, 8 | Delivered jobs can be review-archived without deleting evidence. |
| 10 | `06-18-slice-10-manifest-workflow-regression-gates` | Slice 1-6 | Regression gates prevent schema/script/doc drift. |

Execution should start with Slice 1. Slices 5 and 8 can run after Slice 1 while Slices 2-4 progress. Slice 7 is policy-sensitive and should be confirmed before hardening global reply rules.
