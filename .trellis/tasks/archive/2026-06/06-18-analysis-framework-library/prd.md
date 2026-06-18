# brainstorm: 补齐分析报告规划框架库

## Goal

把分析报告规划从“单一假设驱动”升级为“先按业务问题选择分析拆解框架，再映射报告模板”的可执行机制。框架层需要有项目内真源、可查询 JSON、agent 可读说明和 planning 使用规则，避免 `analysis-plan` 只靠 prompt 文案临场理解。

## What I already know

* 当前报告模板已存在：`executive_onepage`、`summary_structured`、`ranking_report`、`attribution_report`、`competitor_compare`、`technical_detailed`。
* 当前 plan 输出模板已存在：`skills/analysis-plan/references/plan-template.md`。
* 缺口是“分析框架模板”：MECE / Waterfall / OSM / Radar 等此前只出现在 `analysis-plan` 文案里，没有独立文档、结构化配置或可查询实现。
* `skills/analysis-reference/scripts/query_config.py --framework` 原先不读取框架库，导致所有框架查询都返回 `found=false`。
* 用户希望通过网络搜索识别更完整的分析拆解方法，并填充到项目内，解决分析方向单一的问题。

## Assumptions

* 本任务不改 metadata 真源、不改取数和报告生成，只补齐 analysis planning 的框架层。
* 框架层应回答“如何拆问题”，报告模板层回答“如何交付正文”。
* 框架内容必须足够具体，包含适用场景、禁用场景、logic path、目标生成规则、证据需求和推荐报告模板。

## Requirements

* 新增项目内分析框架 registry，能被 `RA:analysis-reference` 查询。
* 新增 agent 可读的分析框架说明文档，包含来源、选型规则和使用边界。
* `query_config.py --framework <id-or-alias>` 必须能命中正式框架，并返回 `logic_path`、`goal_template`、`dimension_type_hints`、`evidence_requirements`、`recommended_templates`。
* 兼容旧入口 `skills/reference-lookup/scripts/query_config.py`。
* 更新 `analysis-plan`，让 planning 按“问题类型 -> 分析框架 -> 交付方式 -> 报告模板 -> 假设验证目标”执行。
* 增加 focused tests 或 smoke，证明框架查询不再是假 miss。

## Acceptance Criteria

* [ ] `python3 skills/analysis-reference/scripts/query_config.py --framework mece` 返回 `found=true`。
* [ ] `python3 skills/analysis-reference/scripts/query_config.py --framework waterfall` 返回 `found=true`。
* [ ] `python3 skills/analysis-reference/scripts/query_config.py --framework funnel` 返回 `found=true`。
* [ ] 未命中时返回 `available_frameworks`，不混入人类 debug 输出。
* [ ] `analysis-plan` 文档不再要求查询不存在的框架配置。
* [ ] 至少有一份 Markdown framework guide 说明如何避免单一分析方向。

## Definition of Done

* Python 脚本通过 `py_compile`。
* 查询 smoke 覆盖核心框架和别名。
* 修改过的文档和输出契约一致。
* 不碰用户已有未提交改动和无关 task。

## Out of Scope

* 不生成实际分析报告。
* 不改报告模板正文格式。
* 不注册或修改 metadata dataset。
* 不做全量行业知识库，只做通用分析规划框架库。

## Research References

* [`research/framework-survey.md`](research/framework-survey.md) — 网络来源筛选和项目落地取舍。

## Technical Notes

* 主要文件：`skills/analysis-reference/scripts/query_config.py`、`skills/reference-lookup/scripts/query_config.py`、`skills/analysis-plan/SKILL.md`。
* 新增真源建议：`skills/analysis-reference/references/analysis-frameworks.json` 和 `analysis-frameworks.md`。
