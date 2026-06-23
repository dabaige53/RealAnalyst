# Job 产物收缩与用户态输出实施拆解

## 拆分原则

这次不要按“schema、脚本、文档、测试”横向拆。那样每个 issue 都做不出完整闭环，最后还是容易出现文档和实现漂移。

应按 tracer bullet 拆：每个 slice 都尽量覆盖一个可验证的端到端行为，从 job 状态记录、产物登记、用户态输出，到验证或兼容 fallback。这样每完成一个 slice，系统就真实变得更干净一点。

## Slice 1：建立 job manifest 最小总账本

**Type**: AFK  
**Blocked by**: None  
**目标**: 新 job 能创建并校验 `job_manifest.json`，先不迁目录、不动旧产物。

### What to build

建立一个最小 job 总入口，记录 job 状态、用户态摘要、artifact 列表和验证状态。这个 slice 只解决“有没有统一总账本”和“能不能安全读写”，不要求所有 skill 立即接入。

### Scope

- 新增 `job_manifest` schema。
- 新增共享读写 helper。
- 支持 init、load、validate、register artifact、update user surface。
- artifact path 必须限制在 job 目录内。
- 写入必须 atomic，避免中途损坏 JSON。

### Acceptance criteria

- [x] 给定一个新 job 目录，可以初始化 manifest。
- [x] 可以登记一个报告 artifact 和一个内部 evidence artifact。
- [x] 用户态清单只返回 `user_visible=true` 的交付物。
- [x] path escape 被拒绝。
- [x] stdout 作为 agent 调用时保持 JSON-only。

### Notes

这是所有后续工作的地基。没有这个 slice，后面改 report/data-profile 都会继续各写各的索引。

---

## Slice 2：analysis-run 初始化和最终回复改成 manifest-first

**Type**: AFK  
**Blocked by**: Slice 1  
**目标**: job 生命周期 owner 开始写 manifest，最终回复默认从 manifest 的用户态摘要生成。

### What to build

`analysis-run` 在创建或恢复 job 时确保 manifest 存在。每轮分析结束时更新 job status、user surface、主交付物、验证状态和下一步建议。最终 completion summary 不再默认列内部路径。

### Scope

- 初始化 job 时创建 manifest。
- 兼容已有 job：manifest 不存在时创建，不移动旧文件。
- 将 `.meta/artifact_index.json` 标记为 legacy 或同步进 manifest。
- 更新 `analysis-run` 的 completion summary 规则：回复默认业务态，技术详情只在用户要求时出现。

### Acceptance criteria

- [x] 新 job 初始化后有 manifest。
- [x] 旧 job 恢复时能生成 manifest，不破坏旧文件。
- [x] 最终回复可由 `user_surface` 渲染出业务摘要。
- [x] 默认回复不包含内部目录、脚本名、source key。

---

## Slice 3：report 输出和文件清单改成 manifest 驱动

**Type**: AFK  
**Blocked by**: Slice 1, Slice 2  
**目标**: 报告不再扫描 job 根目录猜交付物，报告正文和文件清单只展示用户态 artifact。

### What to build

报告生成后登记为 `user_deliverable`。最终附件登记为 `user_attachment`。报告末尾的输出文件清单从 manifest 读取，不再通过 `ls jobs/*.csv jobs/*.md` 生成。

### Scope

- 更新 report skill contract。
- 更新 report output contract。
- report 写入或更新后登记 artifact。
- 输出文件清单只列用户态交付物。
- 内部数据、profile、verification、source context 不进入用户态清单。

### Acceptance criteria

- [x] 报告被登记为 `user_deliverable`。
- [x] 附件只有显式登记为 `user_attachment` 才进入用户清单。
- [x] 报告正文不展示内部路径。
- [x] manifest 缺失时允许 legacy fallback，但必须标记 legacy warning。

---

## Slice 4：report-verify 增加用户态泄露门禁

**Type**: AFK  
**Blocked by**: Slice 3  
**目标**: 报告里出现内部路径、source key、脚本名、工程术语时，默认不能通过交付门禁。

### What to build

在 `report-verify` 增加两类检查：内部路径泄露、内部术语泄露。验证结果写回 manifest 的 `user_surface.verification_status`，但不要求用户阅读 `verification.json`。

### Scope

- 检查绝对路径、`jobs/`、`.meta/`、`profile/`、`internal/`、脚本路径。
- 检查明显 source key / 内部英文 ID / schema 字段泄露。
- 支持技术详情例外：用户明确要求技术信息时允许出现，但必须在 manifest 中有标记。
- 修正 `verification.schema.json` 与实际 check types 不一致的问题。

### Acceptance criteria

- [x] 普通报告出现内部路径时验证失败。
- [x] 普通报告出现系统 source key 时验证失败或警告升级失败。
- [x] 用户要求技术详情时可以豁免指定段落。
- [x] `verification.json` schema 与实际输出一致。
- [x] manifest 中能看到最终验证状态。

---

## Slice 5：data-export / data-profile artifact 登记

**Type**: AFK  
**Blocked by**: Slice 1  
**目标**: 取数和画像产物进入 manifest，但默认不暴露给用户。

### What to build

`data-export` 完成后登记原始导出、取数摘要和可能的用户附件。`data-profile` 完成后登记 profile manifest/profile json 为内部产物。用户态只显示“数据已完成检查/验证”，不显示 profile 文件和 raw data 文件。

### Scope

- data-export 登记 `raw_input`、`supporting_evidence`、必要时 `user_attachment`。
- data-profile 登记 `derived_internal`。
- 修正或替换 `manifest.schema.json`，避免 Tableau-only schema 继续约束通用 profile manifest。
- report/data-profile 读取路径从 manifest 取，旧 job fallback 到旧 summary。

### Acceptance criteria

- [x] 原始导出默认 `internal_only=true`。
- [x] profile 文件默认 `internal_only=true`。
- [x] 用户回复不出现 `profile/manifest.json`。
- [x] 用户附件必须显式登记，不能靠文件名推断。
- [x] 通用 profile manifest schema 与实际输出一致。

---

## Slice 6：analysis-plan 契约和 schema 漂移修复

**Type**: AFK  
**Blocked by**: Slice 1, framework lookup fix  
**目标**: 计划产物、模板锁定、分析框架和 schema 不再互相打架。

### What to build

保留 Markdown plan 作为人类可读分析计划，但 manifest 必须记录它的 artifact 和关键决策字段。当前 `analysis_plan.schema.json` 如果仍描述旧 JSON operator plan，就不能继续被文档说成约束 `analysis_plan.md`。

### Scope

- manifest 记录 plan artifact。
- manifest 记录 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template`。
- 重命名或降级旧 `analysis_plan.schema.json` 说明。
- 新增 Markdown plan contract 或 manifest-level plan decision schema。
- 确认 `analysis-reference --framework` 可命中 `monitoring/diagnosis/benchmark/exploration` 及旧别名。

### Acceptance criteria

- [x] 文档不再声称 Markdown plan 由旧 JSON operator schema 约束。
- [x] plan 的三项模板锁定结果能从 manifest 读取。
- [x] framework 查询返回 `found=true`、`logic_path`、`goal_template`、`dimension_type_hints`。
- [x] report 阶段不重新选模板。

---

## Slice 7：用户态回复规则进入项目级指令

**Type**: HITL  
**Blocked by**: Slice 2  
**目标**: 不只报告，普通聊天回复也遵守用户态输出规则。

### What to build

把“默认不对用户输出内部路径和项目术语”的规则写进项目级 agent 指令、analysis-run completion summary、report skill 和最终回复 checklist。这里需要人工确认边界，因为规则会影响所有后续交互。

### Scope

- 更新项目级说明：聊天回复默认业务态。
- 更新 report/analysis-run completion summary。
- 明确技术详情触发条件。
- 明确哪些场景必须仍给路径：代码修改、测试结果、PR、排障、用户明确问路径。

### Acceptance criteria

- [x] 普通分析交付回复默认不出现内部路径。
- [x] 技术任务仍可给必要文件路径和命令。
- [x] 规则覆盖“报告正文”和“聊天回复”两类输出。
- [x] 用户确认规则边界。

---

## Slice 8：legacy job manifest dry-run 迁移

**Type**: AFK  
**Blocked by**: Slice 1  
**目标**: 旧 job 可以先生成候选 manifest，不移动、不删除文件。

### What to build

做一个 dry-run 迁移工具，扫描旧 job，按文件位置和文件名推断 artifact role，生成候选 manifest 和迁移报告。不确定的文件标为 `unknown_legacy`，不自动清理。

### Scope

- 扫描旧 job。
- 推断 report、CSV、profile、analysis、verification、summary、logs。
- 输出 candidate manifest。
- 输出 review report。
- 不移动、不压缩、不删除。

### Acceptance criteria

- [x] dry-run 不改变旧 job 文件。
- [x] 能生成候选 manifest。
- [x] 不确定文件单列。
- [x] 可作为 job-maintenance 后续审核输入。

---

## Slice 9：delivered job finalize 与内部归档

**Type**: HITL  
**Blocked by**: Slice 1, Slice 3, Slice 8  
**目标**: job 完成后收缩目录噪音，但必须经过确认，不默认删除证据。

### What to build

基于 manifest 做 finalize：确认用户交付物和验证状态后，把 internal 产物移动到内部区或压缩包，manifest 保留 hash、行数、字段、来源和恢复信息。active job 不归档。

### Scope

- 定义 job 状态：active / delivered / archived / failed。
- 定义 safe_to_archive / safe_to_delete。
- 生成 archive review pack。
- 用户确认后移动或压缩 internal。
- manifest 保留恢复索引。

### Acceptance criteria

- [x] active job 不会被归档。
- [x] delivered job 可生成归档候选。
- [x] 未确认前不移动、不删除。
- [x] 归档后 manifest 仍能定位证据或恢复包。

---

## Slice 10：测试与回归门禁

**Type**: AFK  
**Blocked by**: Slice 1-6  
**目标**: 防止这次修完后再次出现文档、schema、脚本三者漂移。

### What to build

补 focused tests 和 smoke commands，覆盖 manifest 读写、用户态清单、泄露检查、schema 与实际输出一致、framework 查询可命中。

### Scope

- manifest helper tests。
- report user-visible artifact tests。
- report-verify leak checks。
- schema-output compatibility tests。
- framework lookup tests。
- pytest 收集规则修正，避免 Tableau 工具脚本被当测试误跑。

### Acceptance criteria

- [x] focused tests 可本地运行。
- [x] `python3 -m compileall` 通过。
- [x] 不需要 Tableau 凭证的默认 pytest 不收集 live Tableau 脚本。
- [x] schema 与脚本输出漂移有测试覆盖。

---

## 推荐执行顺序

1. Slice 1：job manifest 最小总账本。
2. Slice 2：analysis-run 接入和回复降噪。
3. Slice 3：report manifest-first。
4. Slice 4：report-verify 泄露门禁。
5. Slice 5：data-export / data-profile 登记。
6. Slice 6：analysis-plan/schema/framework 契约修正。
7. Slice 7：项目级回复规则确认。
8. Slice 8：旧 job dry-run 迁移。
9. Slice 9：finalize 与归档。
10. Slice 10：测试与回归门禁贯穿收尾。

## 可以并行的部分

- Slice 5 可以在 Slice 2/3 之后并行。
- Slice 6 可以和 Slice 3/4 并行，但依赖 framework lookup 的现有修复。
- Slice 8 可以在 Slice 1 完成后提前做，不必等新流程全部改完。
- Slice 10 的 framework 和 schema tests 可以提前补，但最终要覆盖所有已完成 slices。

## 需要你确认的边界

1. 粒度是否合适：现在拆成 10 个 slice，每个都能独立验收。
2. `Slice 7` 是否要作为硬规则进入项目级 `AGENTS.md`，影响所有回复。
3. `Slice 9` 是否允许未来把 delivered job 的 internal 文件压缩成 archive 包；默认不删除，只压缩和索引。

确认后可以把这些 slice 转成 Trellis 子任务，或继续把每个 slice 扩成完整 PRD。 
