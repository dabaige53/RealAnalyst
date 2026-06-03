# brainstorm: expose semantic reference status

## Goal

让字段、指标、别名搜索和元数据报告都能显式说明“是否引用标准语义”，避免用户只能从 `source_type`、`ref`、`needs_review`、`alias_source` 等底层字段组合推断。

## What I already know

* v0.3.21 已经禁止 dataset 字段/指标继续维护 `standard_id`、`source_field`、`aliases`、`synonyms` 等冗余身份字段。
* 别名搜索已经从 dictionary / mapping / index 层补回，不再要求 dataset YAML 堆别名。
* 当前 `context` 输出仍只有 `source_type`、`ref`、`needs_review`、`source_layer`、`alias_source`。
* 当前 `search/index` 输出仍只有 `source_type`、`ref`、`alias_source`、`canonical_name` 等底层字段。
* 当前 `metadata-report` 只展示“口径状态”，没有单独展示“标准语义引用状态”。
* schema 仍要求 `display_name`，这属于后续“展示中文名重命名/精简”议题；本任务不强行迁移 YAML 字段，避免把运行链路和存储格式同时扩大。

## Assumptions

* 本次不新增 dataset YAML 人工维护字段；`semantic_ref` 由现有 metadata 派生。
* `dictionary` 和 `mapping_override` 都属于“已引用语义层”，但展示文案应区分“标准定义引用”和“映射覆盖引用”。
* `user_confirmed` / `industry_draft` / `inferred` / `pending` 不应被误报成标准引用。

## Remediation Plan

1. 新增统一派生逻辑
   * 在 metadata 公共逻辑中生成 `semantic_ref`。
   * 输出字段包含 `status`、`label`、`ref`、`source_type`、`source_layer`、`confidence`、`needs_review`。

2. 修复 context 输出
   * `fields[]`、`metrics[]`、`glossary[]` 增加 `semantic_ref`。
   * 保留现有 `source_type/ref/needs_review`，但不再要求用户靠它们猜状态。

3. 修复 search/index 输出
   * field / metric / alias / mapping records 增加 `semantic_ref_status`、`semantic_ref_label`、`semantic_ref`。
   * FTS extra text 纳入新状态，便于搜索“标准引用”“映射覆盖”等语义状态。

4. 修复 report 展示
   * 字段表和指标表新增“语义引用状态”列。
   * 映射明细保留“标准语义”，并明确映射本身的语义引用状态。

5. 修复运行态透传
   * `sync-registry` 生成的 runtime spec 保留派生 `semantic_ref`。
   * runtime source context 透传 `semantic_ref_status` / `semantic_ref_label`，避免正式分析链路只剩 `definition_status`。

6. 补测试和文档
   * 验证 context 输出有显式 `semantic_ref.status`。
   * 验证 search alias / metric record 输出有显式语义引用状态。
   * 验证 metadata report 展示“语义引用状态”列和对应文案。
   * 验证 registry spec 和 source context 透传运行态语义引用状态。

## Requirements

* 不恢复 dataset-level `standard_id`、`source_field`、`aliases`、`synonyms`。
* 不要求用户新增 YAML 字段来表达引用状态。
* 输出层必须明确区分：
  * `standard_ref`：引用 dictionary 标准定义。
  * `mapping_ref`：引用 mapping 覆盖或源字段到标准语义映射。
  * `local_confirmed`：本地确认口径，但不是标准语义引用。
  * `local_draft`：本地草稿口径。
  * `inferred`：推断口径。
  * `pending`：待补齐。
* 输出文案必须面向产品/分析用户，不要求读者理解内部字段组合。

## Acceptance Criteria

* [x] `metadata.py context` 的 field / metric 输出包含 `semantic_ref.status` 和 `semantic_ref.label`。
* [x] `metadata.py search` 的 field / metric / alias 输出包含显式语义引用状态。
* [x] `metadata-report` 的核心字段、核心指标和完整明细展示“语义引用状态”。
* [x] `metadata sync-registry` 和 runtime source context 透传运行态语义引用状态。
* [x] 现有 metadata validate 仍通过。
* [x] `tests/test_metadata_product_fixes.py` 增加覆盖并通过。
* [x] 不引入旧冗余字段回流。

## Out of Scope

* 本任务不把 `display_name` 重命名为 `semantic_name`。
* 本任务不迁移所有历史 YAML。
* 本任务不改 release/tag。
* 本任务不创建 GitHub Release。

## Technical Notes

* 重点文件：
  * `skills/metadata/lib/metadata_context.py`
  * `skills/metadata/lib/metadata_index.py`
  * `skills/metadata/scripts/sync_registry.py`
  * `runtime/tableau/source_context.py`
  * `skills/metadata-report/scripts/report_context.py`
  * `docs/metadata-lookup-workflow.md`
  * `docs/semantic-analysis-run.md`
  * `skills/metadata/SKILL.md`
  * `skills/metadata-report/SKILL.md`
  * `skills/metadata/references/yaml-structure-contract.md`
  * `tests/test_metadata_product_fixes.py`
* 当前验证命令：
  * `python3 skills/metadata/scripts/metadata.py validate`
  * `python3 -m pytest tests/test_metadata_product_fixes.py -q`

## Verification Evidence

* `python3 skills/metadata/scripts/metadata.py validate`：通过。
* `python3 skills/metadata/scripts/metadata.py index`：通过。
* `python3 skills/metadata/scripts/metadata.py context --dataset-id demo.retail.orders --field region --metric total_revenue`：输出 `semantic_ref.status` / `semantic_ref.label`。
* `python3 skills/metadata/scripts/metadata.py search --type metric --query revenue --limit 8`：输出 `semantic_ref_status` / `semantic_ref_label`。
* `python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id demo.retail.orders --dry-run`：通过。
* `python3 skills/metadata-report/scripts/generate_report.py --connector duckdb --dataset-id demo.retail.orders --sync-mode metadata-yaml --output-dir /private/tmp/realanalyst-report-check`：报告含“语义引用状态”列。
* `python3 -m pytest tests/test_metadata_product_fixes.py::MetadataProductFixTests::test_registry_metrics_use_canonical_ids_while_export_keeps_source_fields -q`：通过，覆盖 registry spec 和 source context 透传。
* `python3 -m pytest tests/test_metadata_product_fixes.py -q`：47 passed。
* `git diff --check`：通过。

## System Impact Audit

| 链路 | 处理结果 | 证据 |
| --- | --- | --- |
| YAML 真源 | 不新增 `semantic_ref` 维护字段，避免职责漂移 | `rg semantic_ref metadata/datasets metadata/dictionaries metadata/mappings` 无结果 |
| context | fields / metrics / glossary 输出 `semantic_ref` | `metadata.py context` 验证通过 |
| search/index | field / metric / alias / mapping 输出 `semantic_ref_status` / `semantic_ref_label` | `metadata.py search` 验证通过 |
| metadata-report | 核心字段、核心指标、完整明细、映射明细展示“语义引用状态” | report CLI 验证通过 |
| runtime registry | spec metrics / dimensions / filters 透传派生 `semantic_ref` | registry/source context 测试通过 |
| source context | runtime metric context 透传 `semantic_ref_status` / `semantic_ref_label` | registry/source context 测试通过 |
| metadata read | 保持原始 YAML 事实读取；通过 `index_records` 间接包含 index 语义状态 | `metadata_facts.py` 审计 |
| catalog/status | 只做目录/健康状态，不展示字段/指标语义状态 | `build_catalog.py` / `status_registry.py` 审计 |
| OSI export | 交换层，不进入本地需求召回和分析主路径，本次不扩 OSI schema | `metadata_osi.py` 审计 |
