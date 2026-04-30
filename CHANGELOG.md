# Changelog

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
