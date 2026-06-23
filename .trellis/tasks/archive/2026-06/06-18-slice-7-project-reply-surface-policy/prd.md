# Slice 7: 项目级用户态回复规则

## Goal

把“默认不向用户输出内部路径和工程术语”的规则提升为项目级规则，覆盖报告正文和聊天回复。

## Why

用户明确指出问题不只在报告写作，也在普通回复。规则如果只写在 report skill，analysis-run 或其它回复仍会泄露内部细节。

## Scope

- 更新项目级 agent 指令或对应 workflow。
- 更新 analysis-run completion summary。
- 更新 report skill 用户态输出规则。
- 明确技术详情触发条件。
- 明确技术任务例外：代码、测试、PR、排障、用户明确问路径。

## Non-goals

- 不禁止所有技术术语；技术任务仍可使用必要术语。
- 不隐藏用户明确要求的文件路径或复跑命令。

## Acceptance Criteria

- [x] 普通分析交付回复默认不出现内部路径。
- [x] 技术任务仍能给必要路径和命令。
- [x] 规则覆盖报告和聊天回复。
- [x] 用户确认边界后再进入硬规则实现。

## Dependencies

- Slice 2

## Validation

- `python3 -m pytest -q tests/test_analysis_run_manifest_integration.py tests/test_report_manifest_deliverables.py tests/test_report_verify_user_surface.py` （9 passed）
- `python3 -m py_compile skills/analysis-run/scripts/render_user_reply.py skills/report-verify/scripts/verify.py`
- `rg -n "已生成产物：<normalized_request|artifact index|profile JSON|默认不展示内部路径|用户态输出边界|user_surface_leakage" AGENTS.md .trellis/spec/backend/quality-guidelines.md skills/analysis-run/SKILL.md skills/analysis-run/README.md skills/report-verify/SKILL.md`
- completion summary examples updated in `skills/analysis-run/SKILL.md`
- report/user reply checklist updated in `AGENTS.md` and `.trellis/spec/backend/quality-guidelines.md`
- leak check with exception cases covered by `tests/test_report_verify_user_surface.py`
