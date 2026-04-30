# Changelog

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
