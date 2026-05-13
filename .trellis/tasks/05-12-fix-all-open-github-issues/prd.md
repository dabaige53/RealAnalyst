# brainstorm: fix all open github issues

## Goal

修复当前仓库 open GitHub issues（#2-#6），覆盖 metadata-report bootstrap/import、filter validation rendering、guided gap workflow、registry canonical metrics。

## What I already know

* `gh issue list --state open` 返回 #2、#3、#4、#5、#6；#7 按用户最新要求不纳入修复范围。
* #2/#3 集中在 `skills/metadata-report/scripts/generate_report.py` 与 `_bootstrap.py`。
* #4 集中在 dataset-first report 与 connector report 对 runtime spec validation 的读取。
* #5 可复用 `RA:metadata-refine` 的 probe/reference pack 边界，新增 guided workflow。
* #6 集中在 `skills/metadata/scripts/sync_registry.py` 和 `runtime/tableau/source_context.py`。

## Requirements

* Dataset-first metadata report 不 import Tableau-only renderer。
* Project-local installed `metadata-report` 能从 `.agents/skills` layout 定位真实 workspace，并注入 workspace / `.agents` import path。
* Metadata reports 读取 `validation.allowed_values`、`validation.values`、日期范围、数值范围。
* Registry `available_metrics` 只暴露正式 dataset metric id；SQL export 仍保留物理 source fields。
* Source context 能从 runtime spec metrics 解析 display name、source field、expression、aggregation、unit、definition status。
* Metadata refine 增加 guided workflow：基于真实 CSV/profile 生成可审查证据和候选维护建议，可选驱动 validate/index/sync-registry/report loop。

## Acceptance Criteria

* [ ] #2 acceptance criteria satisfied.
* [ ] #3 acceptance criteria satisfied.
* [ ] #4 acceptance criteria satisfied.
* [ ] #5 acceptance criteria satisfied.
* [ ] #6 acceptance criteria satisfied.
* [ ] Focused repository tests pass.

## Definition of Done

* Tests added/updated.
* Docs/skill guidance updated where behavior changed.
* No credentials or runtime samples are written into metadata YAML.

## Out of Scope

* Live Tableau server tests.
* Live ClickHouse connectivity tests.
* Closing GitHub issues before commit/PR.
