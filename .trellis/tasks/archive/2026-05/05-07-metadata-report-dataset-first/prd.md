# brainstorm: dataset-first metadata report

## Goal

把 `RA:metadata-report` 从 connector sync report 视角收敛为 dataset-first 的元数据事实报告。报告面向“准备使用这些数据做分析的人”，只呈现已经维护在 metadata / runtime registry / metadata search 体系里的事实，不推导、不改写、不生成分析用途句。

## What I Already Know

- 用户确认：metadata report 的唯一读者是使用数据做分析的人。
- 用户确认：报告必须尊重事实，直接应用已有 metadata，不做任何更改、推导、补脑或业务含义改写。
- 用户确认：标题、章节、表头和状态标签使用中文；metadata 原始值保持原样。
- 用户确认：系统字段可以显示，但降级为追溯信息，不作为阅读主线。
- 用户确认：metadata report 不生成给 agent 阅读的 JSON context；agent 读取 metadata 时统一调用 metadata search。
- 用户确认：report 不是 search dump。search 是事实入口，report 只做展示编排。
- 用户确认：不读取 `jobs/{SESSION_ID}/profile/*`，不现场跑 profile，不现场查库，不现场采样。
- 用户确认：取值、范围、筛选值只读长期 metadata / runtime registry 已维护事实；没有就写“未维护”。
- 用户确认：默认输出 `metadata/reports/<dataset_id>_metadata_report.md`，默认覆盖最新版，必要时另设 archive/history。
- 现有代码事实：`skills/metadata-report/scripts/generate_report.py` 目前仍以 `--connector duckdb|tableau` 分流，底层 `duckdb_report.py` / `tableau_report.py` 直接读取 YAML、registry/spec/source context 等材料。
- 现有代码事实：`skills/metadata-report/scripts/duckdb_report.py` 当前会在 YAML 报告模式下采样 DuckDB 示例值；新设计要求默认禁止现场采样。
- 现有代码事实：`skills/metadata/scripts/metadata.py search` 已提供统一 search 入口，底层走 `metadata/index/search.db` FTS5，缺失时 fallback 到 JSONL。
- 现有代码事实：`skills/metadata/scripts/metadata.py status` 已提供 dataset 级 metadata/index/runtime registry/export readiness 状态。
- 历史边界：`runtime/registry.db` 是 canonical runtime registry；runtime registry 只存运行态 `entries/specs`，不作为业务定义真源。

## Requirements

### R1. Dataset-first CLI

- 用户主入口应以 `dataset_id` 为核心：

```bash
metadata-report --dataset-id <dataset_id>
metadata-report --all
metadata-report --output-dir <dir>
```

- Connector 不再作为用户主入口。报告内部可根据 search/status/registry 返回的事实判断数据源类型。
- 保留旧 `--connector` 入口时，应作为兼容路径，不成为 README / SKILL 的推荐用法。

### R2. Unified Fact Input

- `metadata-report` 必须通过统一 metadata search/read 能力获取事实，不在 report 层复制一套 YAML / registry 解析逻辑。
- 如果现有 `metadata search` 只能做候选检索，且缺少“按 dataset 精确读取报告事实”的能力，应在 metadata core 增加薄的 search/read API 或 CLI 输出，而不是把解析逻辑塞进 metadata-report。
- search 结果只作为事实输入；Markdown 不能直接 dump search 输出。

### R3. Fact-only Rendering

- 报告只做三件事：
  - 读取事实。
  - 结构化呈现。
  - 标明缺口。
- 禁止：
  - 根据字段名猜业务含义。
  - 根据 role/status 自动生成使用建议。
  - 根据字段结构写“可用于 / 适合 / 建议分析”。
  - 改写 business definition、指标口径、业务边界。
  - 把 sample values 当完整枚举或业务定义。

### R4. Chinese Presentation Contract

- 所有一级标题、二级标题、表格列名、状态标签必须使用中文。
- metadata 原始值保持原样，不翻译、不改写。
- 系统字段必须以中文列名呈现，例如“系统标识”“物理字段”“来源字段”“定义来源”。
- 系统字段只作为追溯信息，不作为阅读主线。

### R5. Section Order

Markdown 章节按以下顺序输出：

1. 元数据事实摘要
2. 数据集信息
3. 字段信息
4. 指标信息
5. 筛选、参数与取值信息
6. 映射与来源追溯
7. 未维护项
8. 运行与注册状态
9. 报告生成信息

- 没有真实内容的 section 不输出。
- 缺失项统一进入“未维护项”。
- 执行链路、生成脚本、validate/status 等审计信息只放末尾。

### R6. Missing Data Rules

- 表格行存在但某个值缺失：对应单元格写“未维护”。
- 整个 section 没有任何真实内容：不输出空 section，在“未维护项”中记录事实缺口。
- “未维护项”只列 metadata 事实缺口，不写建议、影响判断或外部派单语言。

### R7. Values And Ranges

- 取值信息单独成段，不塞进字段主表。
- 分类/文本字段：展示 registry/search 已维护的筛选值或取值列表。
- 数值字段：只展示范围，例如最小值、最大值；不展示一串样本值。
- 日期/时间字段：展示最早日期、最晚日期。
- 如果 registry/search 没有取值或范围：写“未维护”。
- 不读取 job profile；不调用 `RA:data-profile`；不现场查库；不现场采样。

### R8. Unified View With Traceable Sources

- 报告阅读上是统一的“元数据事实视图”，不把正文写成内部架构说明。
- 每条事实应尽量保留来源列，来源可以是 `metadata/datasets`、`metadata/mappings`、`metadata/dictionaries`、`runtime/registry`、`metadata/index/search` 等。
- 业务定义、指标口径、业务边界来自 metadata 事实。
- 注册状态、可取数状态、已维护值域来自 runtime registry / status 事实。
- 若不同来源对同一事实不一致，报告应并列展示来源，不自动裁决。

### R9. Output Location

- 默认输出：

```text
metadata/reports/<dataset_id>_metadata_report.md
```

- 默认覆盖最新版。
- 历史版本如需要，应另设 archive/history 机制，不让分析者在时间戳文件里找最新版。
- 不生成 `*_metadata_context.json` 伴生文件。

### R10. Failure Strategy

- search/read 入口失败：报告生成失败。
- dataset 不存在：报告生成失败。
- registry 不存在或未注册：报告继续生成，对应状态写“未维护”或“未注册”。
- 字段/指标定义缺失：报告继续生成，单元格写“未维护”。
- 整个 section 无内容：报告继续生成，并汇总到“未维护项”。

## Acceptance Criteria

- [ ] `metadata-report --dataset-id <dataset_id>` 可生成 dataset-first Markdown 报告。
- [ ] 报告默认落到 `metadata/reports/<dataset_id>_metadata_report.md`，重复生成默认覆盖。
- [ ] 推荐入口不再要求用户提供 `--connector`。
- [ ] 报告事实通过统一 metadata search/read 能力获取；report 层不复制 YAML/registry 解析主逻辑。
- [ ] 报告不读取 `jobs/*/profile/*`，不现场 profile，不现场查库，不现场采样。
- [ ] 报告不生成 JSON context 伴生文件。
- [ ] 报告标题、表头和状态标签为中文，metadata 原始值不改写。
- [ ] 缺失内容按“未维护”规则展示。
- [ ] 数值字段只展示范围，日期字段只展示起止，分类字段展示已维护取值。
- [ ] 空 section 不输出；缺口进入“未维护项”。
- [ ] 执行/注册/生成信息位于末尾。
- [ ] 旧 connector report 测试若保留，应明确兼容边界；新增测试覆盖 dataset-first 输出契约。

## Definition Of Done

- Tests added/updated for dataset-first CLI, output path, overwrite behavior, no job profile reads, no live sampling, missing data rendering, Chinese headers, and no JSON context output.
- Existing metadata/report tests pass.
- Lint/typecheck or project-equivalent quality checks pass.
- README / SKILL / report template updated to reflect the new dataset-first contract.
- Any compatibility behavior for old `--connector` entrypoints is documented.

## Out Of Scope

- 不重做 `RA:data-profile`。
- 不把 job profile 归档进 metadata。
- 不生成分析计划或业务分析报告。
- 不修改正式 metadata YAML 内容。
- 不建立第二套 metadata context / index。
- 不实现完整 archive/history，除非实现中发现已有本地模式可低风险复用。

## Technical Notes

- Likely impacted areas:
  - `skills/metadata-report/scripts/generate_report.py`
  - `skills/metadata-report/scripts/report_context.py`
  - `skills/metadata-report/scripts/duckdb_report.py`
  - `skills/metadata-report/scripts/tableau_report.py`
  - `skills/metadata-report/SKILL.md`
  - `skills/metadata-report/README.md`
  - `skills/metadata-report/references/report-template.md`
  - metadata search/read helpers under `skills/metadata/scripts/` and `skills/metadata/lib/`
  - tests under `tests/`
- Current `metadata.py search` emits `{success, query, type, backend, matches}` and uses FTS5 when `metadata/index/search.db` exists.
- Current `metadata.py status` emits dataset readiness signals including `metadata_yaml`, `metadata_index`, `runtime_registry`, `runtime_spec`, `export_ready`, and `registry_db`.
- The implementation should treat missing registry/status as reportable facts, not system failures.
- `runtime/registry.db` remains runtime fact source, not business definition source of truth.
