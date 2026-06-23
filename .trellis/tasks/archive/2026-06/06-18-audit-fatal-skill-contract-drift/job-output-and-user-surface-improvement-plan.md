# Job 产物收缩与用户态输出改进方案

## 目标

把 RealAnalyst 的分析 job 从“过程文件散落、agent 和用户都容易看到内部细节”的形态，改成“一个总入口管理全部产物，用户默认只看到业务可读结果”的形态。

最终要达到三个结果：

1. **目录收缩**：每个 job 对外只暴露一个总账本和用户交付物，过程材料进入内部区或归档包。
2. **真源收敛**：agent 不再扫描目录、猜文件、拼路径，而是先读 `job_manifest.json`。
3. **用户输出降噪**：报告和聊天回复默认不出现内部路径、脚本名、英文 source key、schema 字段和工程术语。

这不是“删除过程文件”。RealAnalyst 必须保留取数、画像、分析、验证和证据链，否则会失去复核、复跑和排障能力。正确方向是：**一个 JSON 作为 job 总入口，内部文件可索引、可归档、可恢复，用户侧只看业务交付物。**

## 非目标

本方案不做这些事：

- 不把大 CSV、报告正文、日志全文、profile 明细全部塞进一个巨大 JSON。
- 不删除 raw data、profile、analysis、verification、acquisition log 等可复核证据。
- 不把 Job 变成长期任务管理系统；Job 只记录“本次实际用了什么”，长期项目管理仍由 Trellis task 或其它 task-continuity 结构承担。
- 不让 `metadata`、`runtime registry`、`job artifact` 互相替代。Metadata 管业务含义，Runtime Registry 管能不能取，Job 管本次实际使用和产出。
- 不一次性迁移所有历史 job。先兼容、后迁移、再收紧。

## 当前问题

现在的 job 目录混合了三类内容：

- 用户交付物：报告、最终附件、可分享表格。
- 系统证据：原始导出、画像、分析结构、验证明细、source context、取数摘要。
- 过程状态：计划、timeline、journal、acquisition log、artifact index、临时脚本或中间 CSV。

这些文件都在 `jobs/{SESSION_ID}/` 附近，导致两个后果。

对 agent 来说，多个文件都像“真源”。`analysis_plan.md`、`artifact_index.json`、`export_summary.json`、`profile/manifest.json`、`verification.json`、报告文件都可能被误读成最终入口。于是 agent 会扫描目录、猜路径、重复列文件，甚至把内部调试内容写进报告或回复。

对用户来说，输出里出现大量项目内部信息：本地路径、`.meta`、`profile/manifest.json`、`source_key`、DuckDB/Tableau 内部名、脚本命令、英文 JSON 字段。用户真正关心的是“结论是什么、报告在哪、附件是什么、验证是否通过、风险是什么、下一步做什么”。

## 设计原则

### 1. 单入口，不单文件

`job_manifest.json` 是唯一入口，但不是唯一文件。它记录所有文件、状态、来源、角色和可见性。大文件仍然以文件存在，避免 JSON 过大、难 diff、难恢复。

### 2. 用户态和系统态分层

用户态只包含业务可读内容：中文标题、结论摘要、交付物、验证状态、风险、下一步。

系统态保留工程细节：真实路径、source key、脚本、schema、日志、原始数据、profile、analysis、verification。

### 3. Manifest-first，legacy fallback

新流程必须先读 `job_manifest.json`。旧 job 没有 manifest 时，才允许 fallback 到旧路径，并在 fallback 后生成或建议生成 manifest。

### 4. 明确 artifact 角色

每个产物必须标记角色，避免“所有文件都像交付物”：

- `user_deliverable`：用户可见主交付物，例如最终报告。
- `user_attachment`：用户可见附件，例如最终汇总表。
- `supporting_evidence`：支撑证据，默认不展示。
- `raw_input`：原始输入或原始导出。
- `derived_internal`：系统中间产物，例如 profile、analysis。
- `audit_log`：审计日志。
- `legacy`：旧结构兼容文件。
- `deprecated`：被新文件替代，不再作为入口。

### 5. 默认不泄露内部语言

报告和聊天回复默认不出现：

- 本地绝对路径。
- `jobs/{SESSION_ID}`、`.meta`、`profile/manifest.json` 等目录词。
- Python 脚本名、命令参数、schema 字段。
- Tableau source key、DuckDB 表名、内部英文 ID。
- “我执行了哪些工具”的流水账。

只有用户明确要求路径、复跑、排障、技术审计、代码交接时，才展开技术详情。

## 目标信息架构

推荐目标结构：

```text
jobs/{SESSION_ID}/
├── job_manifest.json
├── deliverables/
│   ├── report.md
│   └── attachments/
└── internal/
    ├── data/
    ├── profile/
    ├── analysis/
    ├── verification/
    ├── logs/
    └── provenance/
```

短期兼容结构：

```text
jobs/{SESSION_ID}/
├── job_manifest.json
├── data/
├── profile/
├── .meta/
├── analysis.json
├── verification.json
├── 报告_*.md
└── 汇总_*.csv / 交叉_*.csv
```

短期不强制移动文件，只要求 `job_manifest.json` 能准确记录这些旧路径，并给每个文件打上 `user_visible` 与 `role`。

## `job_manifest.json` 契约

### 顶层结构

```json
{
  "schema_version": "1.0",
  "job": {},
  "user_surface": {},
  "inputs": [],
  "steps": [],
  "artifacts": [],
  "verification": {},
  "provenance": {},
  "reply_policy": {},
  "archive": {},
  "legacy": {}
}
```

### `job`

记录 job 状态，不记录长期项目状态。

```json
{
  "id": "session id",
  "title": "中文业务标题",
  "status": "planning|running|ready_for_review|delivered|failed|archived",
  "created_at": "ISO time",
  "updated_at": "ISO time",
  "owner_skill": "analysis-run",
  "business_context": "面向用户的简短业务场景"
}
```

### `user_surface`

这是报告和聊天回复的默认来源。

```json
{
  "summary": "一句业务化完成状态",
  "primary_deliverable_id": "artifact_report_main",
  "deliverables": ["artifact_report_main", "artifact_attachment_001"],
  "verification_status": "passed|warning|failed|not_run",
  "risks": [],
  "next_actions": [],
  "display_language": "zh-CN",
  "technical_details_available": true
}
```

### `artifacts`

每个文件都登记为 artifact，但不是每个 artifact 都给用户看。

```json
{
  "id": "artifact_report_main",
  "role": "user_deliverable",
  "kind": "report|csv|json|markdown|log|archive",
  "display_name": "上海区域代理人销售分析报告",
  "path": "deliverables/report.md",
  "user_visible": true,
  "internal_only": false,
  "producer": "report",
  "consumers": ["user", "report-verify"],
  "created_at": "ISO time",
  "status": "ready|superseded|failed|archived",
  "validation": {
    "status": "passed|warning|failed|not_run",
    "verification_id": "verification_latest"
  },
  "safe_to_archive": false,
  "safe_to_delete": false,
  "checksum": "optional"
}
```

规则：

- 用户清单只读取 `user_visible=true` 且 `role in user_deliverable,user_attachment` 的 artifact。
- 内部证据只登记，不默认展示。
- `path` 必须是 job 内相对路径，读取时要做 `resolve + relative_to(job_dir)` 防 path escape。
- 大文件可以只记录 row count、columns、hash、archive ref，不把内容内联进 manifest。

### `steps`

记录阶段，不替代日志。

```json
{
  "id": "step_profile",
  "name": "数据画像",
  "owner_skill": "data-profile",
  "status": "success|warning|failed|skipped",
  "started_at": "ISO time",
  "finished_at": "ISO time",
  "input_artifacts": [],
  "output_artifacts": [],
  "error_code": null,
  "user_visible_summary": "已完成数据质量检查"
}
```

### `reply_policy`

把“聊天回复也不能泄露内部信息”写进 job 级契约。

```json
{
  "default_mode": "business",
  "hide_internal_paths": true,
  "hide_source_keys": true,
  "hide_script_names": true,
  "allow_technical_details_when_requested": true,
  "redaction_notes": []
}
```

## 用户态输出规范

### 聊天回复默认结构

默认回复只保留业务读者需要的信息：

```text
已完成这次分析，核心结论是：<一句业务结论>。

交付物：<中文报告名 / 附件名>。
验证状态：<通过 / 有警告 / 未验证>。
需要注意：<业务风险或待确认口径>。
下一步建议：<1-2 个动作>。
```

如果用户没有要求路径，不写路径。如果用户没有要求复跑，不写命令。如果用户没有要求技术审计，不写脚本名和 JSON 字段。

### 技术详情触发条件

只有以下情况才展开技术详情：

- 用户问“文件路径在哪”。
- 用户问“怎么复跑”。
- 用户要求排障、代码审查、验收证据。
- 当前是 PR、CI、测试失败或开发交接。

技术详情必须单独成段，避免混入业务结论。

```text
技术详情：
- 内部 job：...
- 复跑入口：...
- 验证文件：...
```

### 报告正文规则

报告正文默认只使用中文业务名和可读口径：

- 数据源写业务名称，不写系统 source key。
- 指标写中文展示名；如果展示名与原始字段不同，在口径附录解释，不在正文堆字段名。
- 输出文件清单来自 manifest，不扫描目录手写。
- 内部路径、脚本、schema、JSON 字段不进入主报告。

### 验证门禁

`report-verify` 需要增加两类检查：

1. **内部路径泄露检查**：匹配绝对路径、`jobs/`、`.meta/`、`profile/`、`internal/`、脚本路径。
2. **内部术语泄露检查**：匹配 source key、未解释的英文 ID、脚本名、schema 字段名。

失败策略：

- 用户报告正文出现泄露：`failed`。
- 技术详情段出现且用户明确要求：允许，但必须在 manifest 中标记 `technical_details_requested=true`。

## 各 skill 改造方向

### `analysis-run`

职责：job 生命周期 owner。

改动：

- 初始化 job 时创建 `job_manifest.json`。
- 每个 phase 完成后调用统一 manifest writer 登记 step 和 artifact。
- 最终回复从 `user_surface` 读取，不直接列路径。
- 保留旧 `.meta/artifact_index.json` 一段时间，但标记为 legacy artifact。

验收：

- 新 job 初始化后即存在 manifest。
- job 完成后 manifest 能回答：状态、主报告、附件、验证状态、风险、下一步。

### `data-export`

职责：取数与导出。

改动：

- 导出完成后登记 raw input / export summary / user attachment。
- 原始导出默认 `internal_only=true`。
- 如果某个 CSV 是用户附件，必须显式登记为 `user_attachment`，不能靠文件名判断。

验收：

- report 不再扫描 `data/` 决定附件。
- 用户清单不包含原始导出，除非 plan 明确要求交付原始明细。

### `data-profile`

职责：数据画像。

改动：

- `profile/manifest.json` 和 `profile/profile.json` 登记为 `derived_internal`。
- `user_surface` 只更新一句“数据质量检查结果”，不暴露 profile 文件。
- 修正或替换当前 `manifest.schema.json`，避免 Tableau-only schema 约束通用 profile manifest。

验收：

- 用户回复不再出现 `profile/manifest.json`。
- profiling 结果仍可被 report 和 analysis-run 读取。

### `analysis-plan`

职责：分析计划。

改动：

- plan 仍可保留 Markdown，但 manifest 里必须登记 plan artifact。
- `analysis_plan.schema.json` 不能继续声称约束 Markdown plan；要么改名为旧 JSON operator schema，要么新增 `analysis_plan_markdown_contract.md` / `analysis_plan_manifest.schema.json`。
- plan 输出中的 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template` 同步写入 manifest。

验收：

- schema 与真实产物不再冲突。
- report 阶段从 manifest 或 plan artifact 读模板锁定结果。

### `report`

职责：用户报告。

改动：

- 报告生成前读取 manifest。
- 报告文件写入 `deliverables/` 或登记为 `user_deliverable`。
- 输出文件清单从 manifest 生成。
- 主报告正文不展示系统路径、source key、脚本名。

验收：

- 报告里只出现业务可读交付清单。
- 若缺 manifest，允许 fallback 到旧路径，但必须提示这是 legacy mode。

### `report-verify`

职责：交付门禁。

改动：

- `verification.json` 登记为 internal artifact。
- `user_surface.verification_status` 只写通过/警告/失败，不要求用户读 JSON。
- 修正 `verification.schema.json`，使 check types 和实际脚本一致。
- 增加用户态泄露检查。

验收：

- 任何报告若泄露内部路径或 source key，默认无法通过交付门禁。

### `metadata-refine` / `job-maintenance`

职责：后续维护与归档。

改动：

- refine 读取 manifest 中的 feedback、profile、analysis evidence，不直接扫描 job。
- job-maintenance 基于 manifest 判断哪些文件可归档、哪些仍是 active evidence。
- 归档动作先生成 review pack，用户确认后再移动或压缩。

验收：

- active job 不归档。
- delivered job 可压缩 internal，但 manifest 仍能恢复证据链。

## 新增共享能力

### `runtime/job_manifest.py`

建议新增一个共享模块，而不是各 skill 自己写 JSON。

核心函数：

```python
load_manifest(job_dir) -> dict
create_manifest(job_dir, job_info) -> dict
register_step(job_dir, step) -> dict
register_artifact(job_dir, artifact) -> dict
update_user_surface(job_dir, patch) -> dict
finalize_job(job_dir) -> dict
validate_manifest(job_dir) -> list[str]
```

要求：

- 写入使用 atomic write，避免中途失败损坏 manifest。
- stdout 被 agent 调用时必须 JSON-only。
- 错误返回稳定 `error_code`。
- 所有 artifact path 必须限制在 job 目录内。

### CLI 入口

可以提供一个轻量 CLI：

```bash
python3 runtime/job_manifest.py init --job-dir <job_dir> --title <title>
python3 runtime/job_manifest.py register-artifact --job-dir <job_dir> --path <path> --role <role>
python3 runtime/job_manifest.py user-summary --job-dir <job_dir>
python3 runtime/job_manifest.py validate --job-dir <job_dir>
python3 runtime/job_manifest.py migrate-legacy --job-dir <job_dir> --dry-run
```

## 迁移策略

### 迁移原则

先索引，后移动；先 dry-run，后确认；先新 job，后旧 job。

### 旧 job 迁移流程

1. 扫描旧 job 目录。
2. 按文件位置和命名推断 artifact role。
3. 生成 `job_manifest.json`。
4. 标记不确定项为 `role=unknown_legacy`，不自动删除。
5. dry-run 输出迁移报告。
6. 用户确认后再移动 internal 文件或生成压缩包。

### Legacy fallback

所有读取方在过渡期按这个顺序：

1. 读 `job_manifest.json`。
2. 如果不存在，读旧 `artifact_index.json`。
3. 如果仍不存在，读旧 summary/profile/report 路径。
4. fallback 发生时记录 warning，并建议生成 manifest。

## Rollout 计划

### 7 天：建立最小闭环

产出：

- `job_manifest.schema.json` 初版。
- `runtime/job_manifest.py` 初版。
- analysis-run 初始化 manifest。
- report 输出清单改为 manifest-first。
- report-verify 增加内部路径泄露检查。
- 一个旧 job dry-run migration smoke。

验收：

- 新 job 能生成 manifest。
- 最终回复能从 manifest 生成用户态摘要。
- 报告不会默认展示内部路径。

### 30 天：跑通完整新 job

产出：

- data-export、data-profile、analysis-plan、analysis-run、report、report-verify 全部登记 manifest。
- `artifact_index.json` 降级为 legacy 或被 manifest 包含。
- 修正 `analysis_plan.schema.json`、`manifest.schema.json`、`verification.schema.json` 的契约漂移。
- 增加 focused tests。

验收：

- 从取数到报告验证的完整 job，只读 manifest 就能找到用户交付物和内部证据。
- 普通回复不再输出内部路径、source key、脚本名。
- 技术模式仍可复跑和排障。

### 90 天：归档与维护产品化

产出：

- delivered job 自动 finalize。
- internal evidence 可压缩归档。
- job-maintenance 基于 manifest 出 review pack。
- 旧 job 批量迁移工具稳定。

验收：

- 完成 job 的用户入口只剩 manifest 和 deliverables。
- internal 可恢复，hash/row count/provenance 可核验。
- 项目根目录噪音显著下降，不牺牲可复核性。

## 测试与验收矩阵

| 场景 | 验收 |
| --- | --- |
| 新 job 初始化 | manifest 存在，schema 校验通过 |
| 导出完成 | raw data 登记为 internal，用户附件需显式标记 |
| 画像完成 | profile 登记为 internal，回复不暴露文件名 |
| 报告生成 | report 登记为 user_deliverable |
| 验证完成 | user_surface 更新验证状态 |
| 报告泄露内部路径 | report-verify failed |
| 用户要求技术详情 | 回复允许展示路径，但必须单独成段 |
| 旧 job 无 manifest | fallback 可用，并提示 legacy |
| 旧 job 迁移 dry-run | 不移动文件，只生成候选 manifest 和迁移报告 |
| path escape | manifest validation failed |

## 风险与缓解

最大风险是过度追求干净，导致证据链丢失。缓解方式是：第一阶段只新增 manifest，不移动、不删文件；归档必须经过 dry-run 和确认。

第二个风险是多个 skill 各自写 manifest 导致结构漂移。缓解方式是共享 `runtime/job_manifest.py`，所有写入走同一 helper，并加 schema/test。

第三个风险是用户态输出规则只写在 report skill，聊天回复仍泄露路径。缓解方式是同时改 `analysis-run` completion summary、项目 `AGENTS.md` 或对应 workflow，并把“回复也适用”写成硬规则。

第四个风险是旧 schema 继续误导 agent。缓解方式是把 schema 修复列入 30 天目标，不再让 README 声称 Markdown plan 由 JSON operator schema 约束。

## 第一批实施任务

1. 新增 `schemas/job_manifest.schema.json` 和 `runtime/job_manifest.py`。
2. 修改 `analysis-run` 初始化 job 时创建 manifest。
3. 修改 `report`：交付物登记到 manifest，输出文件清单从 manifest 生成。
4. 修改 `report-verify`：登记验证状态，并检查内部路径/内部术语泄露。
5. 修正现有 schema 漂移：`analysis_plan.schema.json`、`manifest.schema.json`、`verification.schema.json`。
6. 写 `migrate_legacy_job_manifest.py --dry-run`，先只生成候选 manifest，不移动文件。
7. 更新用户态回复规范：报告和聊天回复都默认隐藏内部路径和工程术语。

## 最终判断

这个方向可行，而且应该做。真正的关键不是“只剩一个 JSON 文件”，而是建立一个稳定的 job 总入口，让所有过程文件有角色、有可见性、有归档状态。用户看到的是业务结果，系统保留的是完整证据。这样既能让项目文件夹干净，也能让 agent 不再把工程细节当成交付内容。
