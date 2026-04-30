---
name: "RA:report"
description: |
  Use when: (1) Writing the report after planning and analysis, including continuous follow-up rounds in the same job, (2) Need to execute a locked
  report template, (3) Need to enforce append-only report updates, timeline management, data-source, output-file-list, and appendix rules, (4) Need report
  naming and output decisions to follow the plan contract. Triggers: 报告撰写, report writing,
  模板选择, 输出文件清单, 口径说明, 数据来源, 追加报告, 连续分析.
---

# Report Writing Skill

最终报告的写作入口，保留现有严格质量门槛。主文档只保留工作流与硬规则；模板矩阵、输出契约、附录模板统一下沉到 `references/`。

## 执行前必读依赖

撰写报告前，必须先读取以下文件，不得猜测或补写：

- `jobs/{SESSION_ID}/.meta/analysis_plan.md`：唯一的 plan 契约来源，`artifact` / `filename` / `params` 优先于默认阈值规则。
- `jobs/{SESSION_ID}/.meta/acquisition_log.jsonl`：本 job 每次下载动作的时间线；用于写清“这批数据怎么来的”。
- `jobs/{SESSION_ID}/.meta/artifact_index.json`：job 内正式产物索引；用于确认当前有哪些正式文件、它们分别来自哪一轮。
- `jobs/{SESSION_ID}/.meta/analysis_journal.md`：每轮分析动作、使用文件与新增结论摘要来源。
- `jobs/{SESSION_ID}/.meta/user_request_timeline.md`：用户需求演进来源；用于整理报告中的需求时间线。
- `jobs/{SESSION_ID}/export_summary.json`：Tableau 导出产物清单来源，优先用于确认可用 CSV，禁止猜测固定文件名。
- `jobs/{SESSION_ID}/duckdb_export_summary.json`：DuckDB 导出产物清单来源；若本轮主数据源后端是 DuckDB，优先据此确认正式 CSV。
- `jobs/{SESSION_ID}/profile/manifest.json`：数据集元信息、CSV 列名映射、格式化依据。
- `jobs/{SESSION_ID}/profile/profile.json`：字段语义、role、基数与模板/维度选择依据。

禁止沿用旧路径约定中的根目录 `manifest.json` 或 `profile.json`。

**锁定模板规则（必须）**：
- `analysis_plan.md` 中应优先明确 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template`
- 真正执行时，`selected_report_template` 仍是本次报告模板的直接真源
- 若 `selected_report_template` 不在 `runtime/report_templates.yaml` 的核心 `templates` 中，必须先到 `template_aliases` 解析 `canonical_template`，再按核心模板执行
- 撰写报告时不得重新选择模板
- 若 plan 未明确模板，应回到 planning 阶段补齐，而不是在写报告阶段自行回退

## 配置单一来源（非常重要）

报告模板与业务术语/指标等配置均以 `{baseDir}/runtime/` 为唯一权威来源：

- `runtime/report_templates.yaml`
- `runtime/glossary.yaml`
- `runtime/metrics.yaml`

不要把这些 YAML 复制到 `skills/` 内，避免配置漂移。如需检索模板、术语、指标，优先使用 `RA:reference-lookup` skill 按需查询（metric/glossary 走 SQLite；template/framework 走 YAML）。

**模板上下文使用方式**：
- `template-system-v2.md` 用于理解“先分析模式、再交付方式、最后具体模板”的分层逻辑
- `template-matrix.md` 仅在需要补充理解模板适用场景时再读取
- `runtime/report_templates.yaml` 用于理解“这个模板应该怎么写”
- `references/examples/` 仅在需要模仿该模板写法时再读取
- 最终执行时必须以前置锁定的模板为准，不得重新选择模板

## 连续分析与追加写作（必须）

1. **同一 job 下，报告只允许追加，不允许整篇重写。**
2. 首轮创建主报告；后续所有分析结果都向同一份报告追加。
3. 报告必须显式维护 `需求时间线` 与 `报告更新时间线`，让用户能看见每轮新增了什么。
4. 每轮追加至少补齐：`本轮新增需求`、`本轮新增数据`、`本轮新增分析`、`本轮新增结论`、`基于当前数据还能继续做什么`。
5. 若本轮是修订或纠错，使用“补充说明 / 更正说明”方式追加，不直接覆盖旧内容。
6. 长内容继续文件化交付；聊天框只发摘要、文件说明与下一步建议。

**脚本化建议（推荐）**：在“本轮新增内容”准备好后，用脚本统一做“追加写入 + 时间线维护 + 输出文件清单刷新”：

```bash
./scripts/py skills/report/scripts/append_report_update.py --session-id $SESSION_ID \
  --report-path jobs/$SESSION_ID/报告_<主题>_<时间>.md \
  --request "<本轮用户新增需求一句话>" \
  --update "<本轮新增分析/新增结论一句话>" \
  --append-file <本轮追加内容.md> \
  --refresh-file-list \
  --update-meta-md
```

## 写作硬规范

### 数据描述

用事实、数字、时间范围与口径说话：

- 用：`示例公司共承运 489,664 人次`
- 用：`单位收入 0.31，低于行业均值 0.35`
- 用：`同比下降 27%`
- 不用：`表现良好`
- 不用：`建议加大投入`
- 不用：`这说明市场竞争激烈`

### 结论证据链（必须）

结论、管理结论、建议都必须做到“可复核”。最小要求是“结论 + 证据 + 精简推导”。

`needs_review=true` 的字段或指标只能作为推断口径，不得作为确定事实。报告必须标注为推断口径，并在可用时写入待确认问题或风险；未标注为推断口径时，不得作为确定口径通过验证。

1. 每条结论至少给出 1 个关键数字或对比变化，并写明时间范围与口径。
2. 每条结论必须补上“数据推导”，说明基于哪些数据得到该判断。
3. 若引用阈值或分类标准，必须在 `{baseDir}/skills/report/references/appendix-template.md` 对应的附录表中补齐，并在正文引用该口径名。
4. 无法给出证据或推导时，必须降级为“数据不足/无法计算”，不要输出判断或建议。
5. 报告指标名与数据源不一致时，必须在口径说明中写出“原始指标 -> 展示名”的映射，禁止静默改名。
6. 正文必须直接展示关键问题数据，不能只写结论后把读者推给 CSV。
7. 每条关键结论下方必须紧贴一个小型证据块，优先展示问题对象、风险对象、异常行或 TopN 结果，而不是把 CSV 预览统一堆到报告底部。

推荐写法：

- `结论：{一句话总判断}。证据：{关键数字/对比}。数据推导：{基于哪些数据得到该判断}。`
- `建议：{动作}（触发：{阈值/对象}）。证据：{对应数字}。验证：{指标/目标}。`

### 数字与表述

- 百分比：`85%`、`+3.5%`
- 百分点：`+3pp`
- 大数：`48.9万`、`2.3亿`
- 金额：`680元`
- 趋势：`↑` / `↓` / `→`

## 数据来源与连续分析（必须）

1. 报告前部必须包含 `## 数据来源` 章节，并在这里一次性列出全量来源清单。
2. 同一 job 若后续因用户追加需求引入新 source，必须在 `## 数据来源`、`需求时间线`、`报告更新时间线` 中显式写清是哪一轮新增的。
3. 数据源展示必须中文化，只展示业务名或 `display_name`，禁止在正文暴露系统英文命名。
4. **每一轮分析默认只引用一个主 source。** 同一 job 若跨轮次出现多个 source，也必须按轮次分开记录，禁止无说明混写。
5. `acquisition_log.jsonl` 与 `artifact_index.json` 是报告中“下载方式 / 文件来源 / 轮次关系”的直接依据，不得凭记忆补写。

## 模板执行（必须）

1. 先从 `analysis_plan.md` 读取 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template`
2. 再结合 `skills/report/references/template-system-v2.md` 确认这三者是否匹配
3. 若 `selected_report_template` 是旧模板 ID，先在 `runtime/report_templates.yaml > template_aliases` 中解析 `canonical_template`
4. 再从 `runtime/report_templates.yaml` 读取该核心模板的结构、阅读目标、关键证据要求
5. 再读取 `analysis_plan.md` 中的 `结论级证据块设计`
6. 按模板要求组织正文，不得重新选择模板
7. 若模板要求正文展示关键证据块，必须在对应结论下方直接展示问题行或问题对象，不得把这类证据统一放到报告底部

## 输出与命名（必须）

1. 首轮报告路径固定为 `jobs/{SESSION_ID}/报告_{主题}_{时间}.md`，且文件名必须使用中文；**同一 job 后续轮次继续更新同一路径，不另起新的主报告文件。**
2. 报告正文内必须补齐 `## 输出文件清单`；文件列表只能基于实际生成的产物或 `artifact_index.json` 精确写入，禁止猜写、补想或引用未产出的文件。若文件已同步到 Drive/外部存储，优先在清单中直接写可点击超链接。
3. 所有输出 CSV 的列名必须映射回中文，计算派生字段同样不能保留英文列名。
4. 所有输出 CSV 必须按 `jobs/{SESSION_ID}/profile/manifest.json` 执行格式化。
5. 报告内必须保留 `需求时间线` 与 `报告更新时间线`；每轮追加时，都要把新增需求、数据、分析、结论补进报告，而不是另写一份平行报告。
6. 默认行数阈值、`artifact: csv` 优先规则、清单格式、命名示例见 `{baseDir}/skills/report/references/output-contract.md`。

推荐扫描命令：

```bash
ls -1 jobs/{SESSION_ID}/*.csv jobs/{SESSION_ID}/*.md 2>/dev/null
```

## 引用文件

- `{baseDir}/skills/report/references/template-system-v2.md`：模板体系 2.0 的分层结构、分析模式/交付方式/模板映射；当需要判断 plan 中三层锁定是否一致时优先读取。
- `{baseDir}/skills/report/references/template-matrix.md`：模板适用场景的补充说明；仅在 `analysis_plan.md` 中的模板选择理由不够清楚时再读取。
- `{baseDir}/skills/report/references/output-contract.md`：输出目录、中文命名、行数阈值、`artifact: csv` 契约优先、`## 输出文件清单` 规范。
- `{baseDir}/skills/report/references/appendix-template.md`：`## 口径说明（本次新增/临时）` 附录模板与最小表结构。
- `{baseDir}/skills/report/references/examples/`：关键模板的短示例；仅在需要模仿该模板写法时再读取。

模板详细结构仍以 `runtime/report_templates.yaml` 为唯一权威来源。

## 推荐执行顺序

1. 读取 `jobs/{SESSION_ID}/.meta/analysis_plan.md`、`jobs/{SESSION_ID}/.meta/acquisition_log.jsonl`、`jobs/{SESSION_ID}/.meta/artifact_index.json`、`jobs/{SESSION_ID}/.meta/analysis_journal.md`、`jobs/{SESSION_ID}/.meta/user_request_timeline.md`，先确认这轮是在既有 job 上追加什么。
2. 再按主数据源后端读取 `jobs/{SESSION_ID}/export_summary.json` 或 `jobs/{SESSION_ID}/duckdb_export_summary.json`，以及 `jobs/{SESSION_ID}/profile/manifest.json`、`jobs/{SESSION_ID}/profile/profile.json`。
3. 从 `analysis_plan.md` 读取 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template`，并先对照 `{baseDir}/skills/report/references/template-system-v2.md`。
4. 再回到 `runtime/report_templates.yaml` 取具体模板的章节结构与写作要求。
5. 若 `analysis_plan.md` 中的模板选择理由不足以指导写作，再按需读取 `{baseDir}/skills/report/references/template-matrix.md`。
6. 先判断当前 job 是否已存在主报告：有则追加，无则创建；不得整篇重写旧报告。
7. 按本页硬规范撰写正文，确保所有结论都有证据链，并把本轮新增需求/数据/分析/结论补进时间线。
8. 按 `{baseDir}/skills/report/references/output-contract.md` 决定哪些表嵌入报告、哪些表导出为 CSV；报告落盘后基于实际产物补齐 `## 输出文件清单`。
9. 在报告结尾追加 `## 阅读提示（关键点与注意事项）`，至少说明数据边界、指标口径、是否可外推、适合/不适合用于什么判断。
10. 在报告结尾追加 `## 一段话结论（便于后续看/转述）`，用 1 段话总结最关键结论与使用边界。
11. 只要正文出现本次新增或临时口径，就按 `{baseDir}/skills/report/references/appendix-template.md` 补齐附录。
12. 长内容继续通过文件交付给用户，聊天框只放摘要与下一步建议。

## 核心原则

1. 你自己分析数据，用 LLM 能力理解和组织结论，不依赖脚本代写报告。
2. 每份报告必须同时包含表格和文字分析。
3. 所有结论必须有数据支撑，并写明“证据数据 + 精简推导”，不做主观评价。
4. 报告首先是给用户读的，不是给系统存证的；不得重新选择模板。
5. **同一 job 下报告只追加、不重写。**
6. **报告必须能回看需求演进与更新时间线。**
7. 正文必须承载关键问题数据，CSV 是明细附件，不是正文主载体。
8. 不要在报告底部统一追加 CSV 预览；证据应跟着结论走，而不是跟着文件走。
9. 禁止生成 `pivot.csv` 这类无业务语义的文件名。
10. 严禁删除 `data/` 和 `profile/` 目录。
11. 严禁把子集指标写成总量指标，别名必须显式披露映射关系。

## Completion Summary

报告撰写完成后，向用户汇报：

1. 报告已写入 `jobs/{SESSION_ID}/报告_{主题}_{时间}.md`。
2. 本次生成/追加了哪些章节。
3. 口径说明附录是否已补齐。
4. 输出文件清单是否已更新。
5. 下一步建议：进入 `/skill RA:report-verify` 做交付前门禁检查。
