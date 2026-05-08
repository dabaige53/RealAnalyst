# Changelog

## 0.3.16 - 2026-05-08

- Added a read-only `RA:getting-started` doctor script that fixes project Python, skill base, registry path, DuckDB path, dependency readiness, and recommended next skill before formal work begins.
- Tightened `RA:analysis-run`, `RA:data-export`, `RA:metadata`, and `RA:metadata-refine` boundaries so CSV/header/display-name requests stay in the export layer and do not rewrite dataset YAML identities.
- Standardized dataset YAML field identity rules: `name` remains a stable semantic id, `display_name` holds user-facing names, and `physical_name` / `source_field` hold source columns.
- Extended metadata validation and tests to reject display-name pollution in `fields[].name` / `metrics[].name` while preserving existing dataset responsibility checks.

## 0.3.15 - 2026-05-07

- Added dataset-first metadata reports through `RA:metadata-report` so users can generate reports with `--dataset-id` or `--all` without choosing a connector.
- Added `metadata.py read` and shared metadata fact loading so reports read through the metadata search/read layer instead of duplicating report-local parsing.
- Updated metadata report output to use Chinese headings and tables, default to `metadata/reports/<dataset_id>_metadata_report.md`, avoid JSON context sidecars, and render missing values as `未维护` / `未注册`.
- Tightened tests and spec guidance so metadata reports do not read job profiles, query DuckDB live, or treat numeric/date sample lists as enumerations.

## 0.3.14 - 2026-05-07

- Converted legacy DuckDB and Tableau adapter `generate_sync_report.py` scripts into compatibility wrappers.
- Routed legacy adapter report commands through the unified `RA:metadata-report` generator so old paths follow the metadata/audit isolation contract.
- Added tests to prevent adapter-level report scripts from reintroducing standalone Markdown renderers.

## 0.3.13 - 2026-05-06

- Isolated metadata audit records from report-facing business definitions.
- Added a normalized metadata report context shared by DuckDB and Tableau renderers.
- Tightened metadata reports so missing definitions become explicit YAML补齐项 instead of generated advice or placeholder text.
- Updated the metadata report output contract and tests around definition locations, filters, manifest boundaries, and audit-layer handling.

## 0.3.12 - 2026-05-06

- Restored the Tableau metadata report renderer to the business-first 10-section structure.
- Kept Tableau export validation details embedded inside the technical appendix instead of emitting a separate validation chapter.
- Tightened pending-definition detection and report update append behavior.

## 0.3.11 - 2026-05-06

- Fixed `RA:analysis-reference` template lookup in project-local `.agents/skills` installations.
- Aligned skill count and compatibility docs with the installed `RA:reference-lookup` legacy entrypoint.
- Routed analysis-run metadata lookup guidance through `RA:metadata-search`.
- Cleaned artifact-fusion join docs so keyed joins are the recommended path and index joins are fallback only.

## 0.3.10 - 2026-04-30

- Tightened skill ownership boundaries across metadata, metadata-report, data-export, data-profile, analysis-run, report, and report-verify.
- Made `skills/metadata-report/scripts/generate_report.py` the only public metadata report CLI; DuckDB and Tableau report modules are now internal renderers.
- Updated artifact ownership docs so `runtime/registry.db` is execution-layer source registry, not a business semantic source.
- Clarified Tableau export validation files under `profile/*_{tag}.json` are not official `RA:data-profile` outputs.
- Standardized DuckDB and Tableau pending-definition report text and report filenames around metadata report semantics.

## 0.3.9 - 2026-04-30

- Split metadata synchronization from metadata report generation: connector adapters no longer own Markdown report output.
- Added a unified `RA:metadata-report` script entrypoint for DuckDB and Tableau metadata reports.
- Aligned Tableau report structure with DuckDB while keeping a Tableau-only usage section for `--vf`, `--vp`, view IDs, and export caveats.
- Standardized pending definitions as `业务定义待确认` / `pending` and cleaned formula rendering in report tables.

## 0.3.8 - 2026-04-30

- Added a repo-scoped Codex marketplace at `.agents/plugins/marketplace.json` so teams can add RealAnalyst directly from this repository.
- Documented the marketplace-first install and update flow with `codex plugin marketplace add` and `codex plugin marketplace upgrade`.

## 0.3.7 - 2026-04-30

- Compacted repeated date/time sample values in metadata reports into one representative value plus regex guidance.
- Added reusable metadata value-pattern helpers for date, datetime, month, and date-range formats.
- Wrote regex validation metadata into DuckDB registry specs and Tableau synced specs for filterable time fields.

## 0.3.6 - 2026-04-30

- Added `metadata profile-review` to turn profile/refine evidence into metric, mapping, and sample-profile completeness reports.
- Added `metadata validate --completeness` / `--strict` gates for metric-like fields, metric mappings, and sample-profile evidence.
- Updated skill guidance away from legacy runtime YAML sources and clarified metadata/context/registry responsibilities.
- Improved installer output with requested/resolved version and project skill install/skip/replacement status.
- Lowered `RA:metadata-refine` friction for metadata-only workflows and made DuckDB export summaries unique per export.
- Fixed DuckDB metadata reports so confirmed metric definitions override matching metric-source field definitions and review counts do not double-count them.

## 0.3.5 - 2026-04-30

- Added `RA:metadata-refine` to turn job feedback, profile output, and real-data probes into archived metadata reference packs.
- Added `metadata_feedback.jsonl` to analysis jobs so analysis can record metadata issues without modifying YAML.
- Documented the handoff from `RA:metadata-refine` reference packs to `RA:metadata` YAML maintenance.

## 0.3.4 - 2026-04-30

- Added DuckDB metadata report read-only sample value collection for filterable fields.
- Updated `RA:metadata-report` guidance and templates to show sample values without treating them as business definitions.
- Published the skill changes that were already validated in an installed project copy.

## 0.3.3 - 2026-04-30

- Removed legacy `schema_note` generation from metadata enrichment.
- Stopped exposing schema-only notes in metadata index, search, and context payloads.
- Tightened validation so connector structure notes cannot become business definitions.
- Refreshed the demo DuckDB metadata report without the old `Schema 说明` column.

## 0.3.2 - 2026-04-30

- Removed legacy `schema_note` / `Schema 说明` from DuckDB metadata reports and review-gap reports.
- Added installer output for the actual installed plugin version and commit.
- Tightened update-guide checks so version mismatches and report-layer legacy fields are visible.

## 0.3.1 - 2026-04-30

- Pointed upgrade checks to online RealAnalyst guides so target projects are not expected to contain repository docs.
- Clarified that installer-managed `runtime/` support files are separate from generated `runtime/registry.db`.
- Added the online update guide URL to installer output.

## 0.3.0 - 2026-04-30

- Unified runtime storage around a single `runtime/registry.db` for source registry and lookup tables.
- Added FTS5-backed metadata search with JSONL fallback, plus catalog and reconcile metadata commands.
- Added multi-dataset context packs, source-group registry helpers, and clearer skill interaction documentation.
- Expanded `RA:metadata-report`, `RA:analysis-run`, and runtime docs for open-source usage and controlled artifacts.

## 0.2.8 - 2026-04-30

- Added `metadata enrich-definitions` to backfill dataset business definitions from mapping overrides and shared dictionaries.
- Tightened validation so connector schema notes, same-name fields, and DuckDB/Tableau placeholders cannot pass as business definitions.
- Added reusable definition resolution helpers and a pending-definition review report writer for fields that still need user confirmation.

## 0.2.7 - 2026-04-30

- Improved `RA:metadata-report` so DuckDB reports can be generated directly from `metadata/datasets/*.yaml` with `--dataset-id`, `--source`, or `--all-yaml`.
- Expanded DuckDB metadata reports with field evidence, metric details, `sql_where` candidates, mapping summaries, and review gaps.
- Clarified that DuckDB YAML reports do not write `registry.db`; runtime registry reports remain available through `--key` / `--all`.

## 0.2.6 - 2026-04-30

- Added `RA:metadata-report` for Tableau/DuckDB metadata Markdown reports with script-first generation guidance and reusable report templates.
- Added installer version strategy support so installs can follow `latest` or pin a fixed release tag.

## 0.2.5 - 2026-04-30

- Refined `RA:metadata` into a lighter execution entrypoint while keeping key operating model, decision rules, quality gates, and common mistakes in the skill file.
- Moved detailed YAML structure, maintenance contracts, and Tableau/DuckDB adapter guidance behind focused `references/` documents.
- Improved metadata registry sync output by separating source measures from semantic metrics and deduplicating available metric names.

## 0.1.0 - 2026-04-28

Initial public release.

- Added metadata-first Codex skill suite for autonomous data analysis.
- Consolidated metadata operations into the `metadata` skill.
- Moved Tableau and DuckDB discovery into metadata connector adapters.
- Added YAML metadata source, lightweight index, context pack, and OSI export flow.
- Added skill names for analysis planning, analysis running, data profiling, reporting, and report verification.
- Added getting-started guidance and public repository layout notes.
