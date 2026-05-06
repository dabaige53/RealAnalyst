# Phase 3 Analysis Contract

## 硬约束

| 禁止操作 | 原因 |
| :--------------------------------- | :----------------------------- |
| 无记录地反复重取同一份数据 | job 内无法追溯取数动作 |
| 不经确认就新增数据源 | 越过用户授权边界 |
| **脑补/编造数字** | **所有数据必须来自正式 CSV 或其正式衍生结果** |
| **脱敏/替换真实数据** | **严禁用虚构值替代真实数据** |
| **捏造代理人/公司名称** | **严禁使用"某公司"等脱敏表述代替真实分析对象** |

**🚨 数据真实性铁律（违反立即终止）**：

- **禁止捏造**：所有数字、名称、日期必须 100% 来自 CSV 原始数据或正式衍生结果。
- **禁止脱敏**：严禁将真实公司名替换为"某公司A""代理人X"等。
- **禁止猜测**：数据不存在就说"无数据/当前数据不足"，不得推测或补全。

## 连续分析数据边界

**可以直接继续**：

- 修正报告文字、补充引用
- 基于当前 job 已下载数据做继续分析、继续下钻、继续生成汇总表
- 在同一 job 内补下**同一数据源**的数据，只要已记录补数原因、筛选条件、输出文件与时间
- 对重复出现的派生分析（如月度综合表现、Top/Bottom 识别、周期对比），优先固化为 workspace 脚本或 skill 脚本，再执行

**必须先向用户确认**：

- 当前数据回答不了新问题，且需要**新增数据源**
- 当前问题已明显越出原分析范围，需要引入新的对象、口径或数据域
- 需要把不同 source 的结果放到同一轮结论中一起使用

**发现数据不足时**：

- 若当前数据足够回答，直接继续分析
- 若补同一数据源即可回答，记录元数据后补数并继续
- 若必须新增数据源，先向用户说明原因与计划，等待确认后再执行
- 若用户未确认新增数据源，则在报告中添加「数据限制说明」，并停在当前可回答范围

## 分析执行流程

1. **先读取 job 当前状态**：优先看 `artifact_index.json`、`acquisition_log.jsonl`、`user_request_timeline.md`。
2. **再确认正式产物清单**：Tableau 路径读 `export_summary.json`；DuckDB 路径读 `duckdb_export_summary.json`；禁止猜测固定文件名。
3. **再读取 `analysis_plan.md`**：按 plan 中声明的目标产物和下钻路径锁定需要打开的文件。
4. **最后按精确路径读取**：`artifact_index / 正式产物清单` → `analysis_plan.md` → exact file reads。
5. **读取 `profile/profile.json`**：识别字段语义、role（metric/dimension）。
6. **执行分析**：优先复用当前数据；补数或新增数据源严格按上方边界处理。
7. **追加到既有报告**：不得整篇重写，必须保留旧内容。
8. **更新 `analysis_journal.md` 与 `user_request_timeline.md`**。
9. **向用户做阶段性说明**：当前数据 / 已做分析 / 可继续方向 / 是否需要确认新数据源。
10. **生成 `analysis.json`**：分析完成后必须写入，缺失导致 `RA:report-verify` 无法运行。

## analysis.json 产出契约

结构遵循 `{baseDir}/schemas/analysis.schema.json`，至少包含：

```json
{
  "job_id": "{SESSION_ID}",
  "dataset_id": "<metadata dataset id>",
  "created_at": "<ISO 8601>",
  "analysis_type": "<executive_summary | trend_analysis | comparison | deep_dive | forecast>",
  "findings": [
    {
      "id": "f_001",
      "type": "ranking | trend | comparison | anomaly | correlation | summary",
      "claim": "结论声明（自然语言）",
      "value": 12345,
      "unit": "人次",
      "metric": "CSV 列名",
      "dimension": "分组依据",
      "evidence": {
        "source_file": "data/<正式CSV>.csv",
        "calculation": "SUM(col) GROUP BY dim",
        "row_indices": [1, 2, 3]
      },
      "confidence": 0.95
    }
  ],
  "statistics": {
    "<operation_id>": {
      "total": 100000,
      "top_items": [{"name": "...", "value": 50000}],
      "trend_label": "up | down | flat",
      "delta_pct": 12.3
    }
  }
}
```

**规则**：

- 每条分析结论必须对应一个 `finding`，`id` 格式 `f_001` 递增。
- `evidence.source_file` 必须指向 `jobs/{SESSION_ID}/` 内的实际文件路径。
- `statistics` 保存聚合统计结果，用于 `RA:report-verify` 的排名一致性和趋势方向校验。
- 连续分析场景下，后续轮次向同一 `analysis.json` 追加新 findings，不覆盖已有条目。
- `needs_review=true` 的口径对应的 finding 必须设置 `confidence < 0.7`。

## 文件选择规则

- 目录扫描只作为检查点，不作为命名推断依据
- 禁止使用 `read` 读取 `jobs/{SESSION_ID}/data/*.csv` 原始导出文件；原始数据只允许通过 profiling、`head`、`grep`、采样或聚合命令间接查看
- 允许读取加工后的分析产物 CSV，例如 `汇总_*.csv`、`交叉_*.csv`
- 允许读取 job 内元数据文件（artifact_index.json、acquisition_log.jsonl、analysis_journal.md、user_request_timeline.md）
- 禁止猜测固定文件名
- 缺少文件时先核对 `export_summary.json` / `duckdb_export_summary.json`、`artifact_index.json` 与 plan 契约，不能直接重导出
