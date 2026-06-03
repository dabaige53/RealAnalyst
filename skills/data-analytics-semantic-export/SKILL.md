---
name: RA:data-analytics-semantic-export
description: Use when RealAnalyst metadata needs to be exported into a Data Analytics semantic-layer skill package for later Data Analytics analysis, source selection, metric lookup, or dashboard/report handoff. Do not use for writing Data Analytics user-context automatically, modifying Data Analytics plugin files, or changing RealAnalyst canonical metadata.
---

# RA:data-analytics-semantic-export

把 RealAnalyst 项目内 metadata 导出成 Data Analytics 可读取的 semantic-layer skill package。这个 skill 只做语义投影和交接，不修改 Data Analytics 插件，不自动写 Data Analytics `user-context`，也不改正式 metadata。

## When To Use

- 用户要把 RealAnalyst metadata 成果交给 Data Analytics 做后续分析、report 或 dashboard。
- 已有一个或多个 RealAnalyst dataset，需要生成 Data Analytics semantic-layer 指导：metrics、fields、dimensions、filters、source inventory、caveats 和 provenance。
- 需要把 RealAnalyst 的项目本地语义真源投影成全局 Data Analytics 可复用 skill。

## Do Not Use

- 不用于注册、修正或补齐 RealAnalyst metadata；这仍由 `RA:metadata` / `RA:metadata-refine` 负责。
- 不用于取数、画像、写报告或验证报告；这些仍由 `RA:analysis-run` 及其流程内 skill 负责。
- 不修改 Data Analytics 插件文件。
- 不自动写 `$CODEX_HOME/state/plugins/data-analytics/user-context.md`。
- 不输出 secrets、DSN、token、row-level sample 或长私有摘录。

## Output Contract

默认输出到全局：

```text
$CODEX_HOME/skills/<area-slug>-semantic-layer/
```

如需避免同名冲突，必须由用户显式传入 `--skill-name`；本 skill 不自动追加项目名前缀。

生成文件：

```text
SKILL.md
references/semantic-layer.md
references/source-inventory.md
```

RealAnalyst 项目内 `metadata/datasets`、`metadata/dictionaries`、`metadata/mappings`、`metadata/sources`、`metadata/audit`、`runtime/registry.db`、`jobs/` 仍是正式语义真源。全局 semantic-layer 只是从 RealAnalyst metadata 导出的使用副本；两者不一致时，以 RealAnalyst metadata 为准。

## Workflow

1. 确认 `--area` 和一个或多个 `--dataset-id`。如果范围跨多个业务区，拆成多个 semantic-layer package。
2. 先检查 RealAnalyst metadata 是否已维护到可导出状态。至少运行或确认已运行：

   ```bash
   python3 skills/metadata/scripts/metadata.py validate
   ```

3. 运行导出脚本。测试或预览时必须显式传 `--output-dir`，避免写入全局：

   ```bash
   python3 skills/data-analytics-semantic-export/scripts/export_semantic_layer.py \
     --area <area> \
     --dataset-id <dataset_id> \
     --output-dir <temp_or_target_package_dir>
   ```

4. 读取 stdout JSON summary，重点检查：
   - `output_path`
   - `files_written`
   - `datasets`
   - `suggested_user_context_entry`
   - `data_analytics_validation_prompt`

5. 人工检查生成的 `references/semantic-layer.md` 和 `references/source-inventory.md`，确认字段映射、指标、source objects、grain/time fields、caveats、open questions 和 provenance paths 都来自 RealAnalyst metadata / runtime。

6. 如需让 Data Analytics 长期发现该 semantic-layer，只能在用户明确批准后，把 summary 里的 `suggested_user_context_entry` 作为指针写入 Data Analytics 全局 `user-context`。默认不写。

7. **Data Analytics 子代理校验**：完成导出后，必须派一个独立子代理或独立检查 pass，显式加载 Data Analytics 的 semantic-layer setup/template/source-intake 要求和生成 package，检查输入数据、字段映射、指标、source inventory、caveats、open questions、provenance 是否一致，并确认它能被 Data Analytics 后续分析使用。这个步骤写在工作流中执行，不要写进导出脚本自动启动子代理。

## Completion Summary

- 完成情况：报告生成的 package 路径、文件清单和覆盖的 dataset id。
- 下一步建议：如需长期启用，提示用户批准后再注册 Data Analytics `user-context` 指针。
- 边界提醒：RealAnalyst metadata 仍是正式真源；semantic-layer 是使用副本，不能替代 Data Analytics 的 live source verification。
