# Skills 与元数据全量审计报告

## Goal

对 `skills/` 下全部 Skill、其构建代码、跨 Skill 交付链路，以及全项目元数据文件做一次深度人工审计，产出一份独立的审计报告（Markdown），覆盖用户提出的 6 个维度，并对每个发现给出严重级别、证据（`file:line`）和修复建议。

本任务交付的是**审计结论报告**，不是新的审计工具；现有 `scripts/audit_project_contracts.py` 已提供自动化契约校验（当前全绿），本次审计要找的是自动化校验覆盖不到的问题。

## Scope

审计对象：

- 全部 Skill（`skills/*/`）及 `skills/README.md`。
- 每个 Skill 的 `SKILL.md`、`README.md`、`references/`、`scripts/`、`lib/`。
- 全项目元数据：`metadata/`、`schemas/`、`runtime/`、`skills-lock.json`、`jobs/` 产物样例。
- 测试：`tests/`、`test.sh`、`scripts/audit_project_contracts.py`。

## Requirements

按用户 6 个维度组织发现：

1. **SKILL.md 与构建代码的一致性**：SKILL.md 声明的命令、脚本路径、参数、输入输出契约，与 `scripts/`、`lib/` 实际实现是否一致；引用的脚本/文件是否真实存在；命令示例能否跑通。
2. **代码问题**：脚本中的逻辑缺陷、异常处理、路径假设、schema 校验缺口、与 CLAUDE.md/AGENTS.md 约定的偏离。
3. **Skill 间交付物断档**：上游 Skill 产出的 artifact（job_manifest、profile、export_summary、analysis_plan、verification 等）是否被下游正确消费；handoff 契约是否连续、可衔接，有无孤儿产物或缺失的衔接步骤。
4. **元数据交付卡点/脏内容**：metadata 文件中是否存在未被引用的文件、断链、被禁止的字段（参考 `FORBIDDEN_DATASET_KEYS`）、过期/脏内容、未关闭的卡点。
5. **测试覆盖**：每个 Skill 的代码、交付物、关联信息是否有测试脚本验证；找出无测试覆盖的实现面与交付链路。
6. **隐藏 bug**：上述维度之外的隐性问题（边界条件、异常处理、时间/随机性假设、跨平台路径、编码、并发等）。

## Constraints

- 审计过程只读，不修改被审计的代码与元数据（报告本身除外）。
- 不连接真实数据源（Tableau/DuckDB/MySQL/ClickHouse）或生产凭证。
- 报告交付物：`tests/reports/2026-06-19-skills-metadata-full-audit.md`（独立报告）。
- 报告正文用简体中文；技术名词/路径/命令保留英文。
- 每个发现必须含：维度、严重级别（P0/P1/P2/P3）、证据（`file:line`）、影响、修复建议。

## Acceptance Criteria

- [x] 报告覆盖全部 Skill，且 6 个维度每个都有明确结论（有问题列问题，无问题写明"已核查通过"）。
- [x] 每个发现都可定位到 `file:line` 证据，并给出严重级别与修复建议。
- [x] 报告包含一张"Skill × 维度"覆盖矩阵，便于快速定位。
- [x] 报告区分"自动化审计已覆盖"与"本次人工新发现"，不与现有 `audit_project_contracts.py` 结论重复造轮子。
- [x] 跨 Skill 交付链路（getting-started → metadata → analysis-run → analysis-plan → data-export/data-profile → report → report-verify）有端到端断档分析。
- [x] 报告给出一份按严重级别排序的"建议修复清单"作为收尾。
- [x] 现有测试套件（`test.sh` / 104 tests）在审计前后保持全绿（基线确认）。

## Notes

- 基线现状（审计起点）：`audit_project_contracts.py` → success=True / 0 findings / 无未引用脚本；`unittest discover -s tests` → 104 passed。
- 本次审计目标是发现**自动化校验覆盖不到**的问题，重点在跨 Skill 衔接、文档-代码漂移、脏/孤儿内容、隐藏边界 bug。
