---
name: "RA:metadata-refine"
description: Use when analysis jobs, user feedback, profile outputs, or real-data probes need to be converted into reference materials for later RA:metadata maintenance; trigger for metadata 修正材料, 字段定义不清, 指标口径待修, evidence 补充, job feedback, profile-based metadata refinement.
---

# Metadata Refine Skill

`RA:metadata-refine` 只生成元数据修正参考材料。它读取分析 job、用户反馈、profile 和必要的数据探查结果，把问题整理成可审查文件；正式 YAML 仍由 `RA:metadata` 维护。

## When to Use

使用本 skill：

- 用户反馈字段定义、指标口径、证据来源或 review 标记有问题。
- 分析 job 中记录了 metadata 相关问题，需要整理成修正材料。
- 需要基于真实 CSV / profile 补充字段观察、样例值、枚举候选、空值率或类型信号。
- 需要把临时 refine 材料归档到 `metadata/sources/refine/`，供 `RA:metadata` 引用。

不要使用本 skill：

- 直接修改 `metadata/datasets/*.yaml`、`metadata/mappings/*.yaml` 或 `metadata/dictionaries/*.yaml`。使用 `RA:metadata`。
- 执行正式分析、写报告或生成业务结论。使用 `RA:analysis-run` / `RA:report`。
- 发布 index 或同步 `runtime/registry.db`。使用 `RA:metadata validate/index/sync-registry`。
- 把 profile、sample values、enum candidates、nullable、physical type 或 source mapping 写回 dataset YAML。

## Workflow

1. 记录或读取分析反馈：

```bash
python3 {baseDir}/skills/metadata-refine/scripts/collect_feedback.py --session-id <SESSION_ID> --list
python3 {baseDir}/skills/metadata-refine/scripts/collect_feedback.py --session-id <SESSION_ID> --issue-type field_definition_unclear --summary "字段含义需要确认"
```

2. 如需看真实数据，基于 job 内正式 CSV 做轻量探查：

```bash
python3 {baseDir}/skills/metadata-refine/scripts/probe_data.py --session-id <SESSION_ID> --data-csv jobs/<SESSION_ID>/data/<file>.csv --dataset-id <dataset_id>
```

metadata-only 场景没有 analysis job 时，也可以直接传 dataset 和 CSV：

```bash
python3 {baseDir}/skills/metadata-refine/scripts/probe_data.py --dataset-id <dataset_id> --data-csv <file>.csv
```

3. 生成参考材料包：

```bash
python3 {baseDir}/skills/metadata-refine/scripts/build_reference_pack.py --session-id <SESSION_ID> --dataset-id <dataset_id>
python3 {baseDir}/skills/metadata-refine/scripts/build_reference_pack.py --dataset-id <dataset_id> --data-csv <file>.csv --profile-json <profile.json>
```

默认输出到：

```text
runtime/metadata-refine/{refine_id}/
  refine_brief.md
  refine_followup.md
  feedback_summary.md
  data_probe_summary.md
  metadata_update_reference.md
  evidence_manifest.json
```

4. 完成后归档，不在 runtime 长期保留：

```bash
python3 {baseDir}/skills/metadata-refine/scripts/archive_reference_pack.py --refine-id <refine_id> --session-id <SESSION_ID>
```

归档后位置：

```text
metadata/sources/refine/{refine_id}/
```

5. 交给 `RA:metadata` 继续维护 YAML：

```text
/skill RA:metadata
基于 metadata/sources/refine/{refine_id}/ 的参考材料修正对应 metadata YAML，并运行 validate/index/sync-registry。
```

## Boundaries

- `runtime/metadata-refine/` 是临时工作区。
- `metadata/sources/refine/` 是归档证据区。
- `evidence_manifest.json` 必须记录 `job_id`、输入 CSV、profile、feedback 和归档路径；正式 YAML 只能通过 `business_definition.ref` 引用关联记录，不复制 evidence。
- 参考材料可以提出建议，但不得声明为已确认口径。
- profile 输出只允许留在 `runtime/metadata-refine/` 草稿区或归档后的 `metadata/sources/refine/`；不得自动生成 dataset YAML patch。
- 枚举候选、样本值、空值率和物理类型只能作为 registry upsert / data_probe 建议，不得写成 `enum_values`、`sample_profile`、`sample_values`、`top_values`、`duckdb_type` 或 `nullable` 字段。
- 发现 source 字段映射时，只生成 `metadata/mappings/*.yaml` 维护建议，不在 dataset fields/metrics 内嵌 `source_mapping`。
- 如果材料含样例值或业务敏感信息，归档前必须先脱敏或确认该项目允许保存。

## Completion Summary

完成后用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已读取来源：<job、profile、CSV、feedback、用户反馈>
- 已生成 refine pack：`metadata/sources/refine/{refine_id}/`
- 已生成参考文件：<evidence_manifest.json、metadata_update_reference.md、refine_followup.md>

下一步建议：
- 最推荐下一步：/skill RA:metadata ...（基于 refine pack 修正正式 YAML）
- 可选下一步：/skill RA:metadata-report ...（修正后生成长期口径说明）
- 可选下一步：/skill RA:analysis-run ...（下一次分析复用更好的 metadata）

边界提醒：
- 本 skill 只整理和归档参考材料，没有直接修改正式 YAML。
- 正式写回必须由用户主动进入 /skill RA:metadata，并运行 validate / index / sync-registry。
```
