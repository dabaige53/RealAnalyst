# Slice 10: manifest 工作流回归门禁

## Goal

补 focused tests 和 smoke commands，防止文档、schema、脚本再次漂移。

## Why

这次暴露的问题本质是契约漂移。没有回归门禁，后续还会出现“文档说能返回，脚本永远 miss”或“schema 和真实输出不匹配”。

## Scope

- manifest helper tests。
- user-visible artifact tests。
- report leak checks。
- schema-output compatibility tests。
- framework lookup tests。
- pytest collection safety，避免 live Tableau 工具脚本被默认 pytest 误收集。

## Non-goals

- 不做全量端到端真实 Tableau 测试。
- 不要求所有旧 job 一次性通过新 manifest schema。

## Acceptance Criteria

- [x] focused tests 可本地运行。
- [x] `python3 -m compileall` 通过。
- [x] 默认 pytest 不收集需要 Tableau 凭证的 live 工具脚本。
- [x] schema 与脚本输出漂移有测试覆盖。

## Dependencies

- Slice 1-6

## Validation

- `python3 scripts/run_manifest_workflow_regression.py` （24 passed, 9 subtests passed）
- `python3 -m compileall -q skills runtime scripts .trellis/scripts` covered by regression script
- focused pytest suite covered by regression script
- schema smoke covered by regression script
- no-live-credential pytest collection smoke covered by focused pytest path list in regression script; live Tableau scripts are not collected as tests
