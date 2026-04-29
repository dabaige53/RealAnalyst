---
name: data-profile
description: |
  Use when: (1) Starting analysis to understand dataset structure, (2) Checking data quality before
  processing, (3) Need schema, semantic roles, null counts, and signals before analysis, (4) Need to bind a profiling result back to a specific CSV inside a continuous-analysis job. Triggers:
  profiling, 数据画像, 数据概览, profile, 数据质量, schema summary.
---

# Profiling Skill

生成数据集的正式画像产物。当前业务语义注入（metrics）运行时真源为 `runtime/runtime_config.db`（不再回退读取 `runtime/metrics.yaml`）：

- `profile/manifest.json`：schema、lineage、profile_summary
- `profile/profile.json`：signals、quality、statistics

## 用法

```bash
python3 {baseDir}/skills/data-profile/scripts/run.py
python3 {baseDir}/skills/data-profile/scripts/run.py --data-csv <data_csv>
python3 {baseDir}/skills/data-profile/scripts/run.py --output-dir <output_dir>
python3 {baseDir}/skills/data-profile/scripts/profile.py <data_csv> <output_dir>
python3 {baseDir}/skills/data-profile/scripts/profile.py --help
```

推荐入口是 `run.py`：

- 默认通过 `SESSION_ID` 推导 `jobs/{SESSION_ID}` 作为输出目录
- Tableau 路径：默认从 `export_summary.json` 解析本轮唯一成功导出的正式 CSV
- DuckDB 路径：默认从 `duckdb_export_summary.json` 读取 `output_file` 作为正式 CSV
- 若存在多个成功导出文件，必须显式传 `--data-csv`，禁止猜测固定文件名

`profile.py` 保留为底层执行器，适合手工指定 `data_csv` 与 `output_dir` 的高级用法。

## 参数

`run.py` 参数：

| 参数 | 说明 |
|------|------|
| `--data-csv` | 显式指定输入 CSV；传入后不再读取 `export_summary.json` / `duckdb_export_summary.json` |
| `--output-dir` | 显式指定输出目录；未传时默认使用 `jobs/{SESSION_ID}` |

`profile.py` 参数：

| 参数 | 说明 |
|------|------|
| `data_csv` | 输入数据文件路径，优先使用 `export_summary.json` 或 plan 契约里声明的正式 CSV |
| `output_dir` | 输出目录 |

## 输出文件

| 文件 | 作用 |
|------|------|
| `profile/manifest.json` | 数据集元信息、schema、lineage、profile_summary；必须能回溯到输入 CSV |
| `profile/profile.json` | 详细画像、signals、quality、statistics；默认代表当前 job 最新一轮 profile |

完整字段说明与 JSON 示例见 `{baseDir}/skills/data-profile/references/output-schema.md`。
大文件读取、采样与 token 控制规则见 `{baseDir}/skills/data-profile/references/large-file-rules.md`。

### 质量评分标准

| 评分 | 条件 |
|------|------|
| 1.0 | 无空值、无异常 |
| 0.9+ | 空值率 < 1% |
| 0.7-0.9 | 空值率 1-5% |
| < 0.7 | 空值率 > 5% 或存在严重质量问题 |

## 连续分析与来源绑定

1. Profiling 结果必须绑定到**明确的输入 CSV**，不得出现“只有 profile，没有来源文件”的情况。
2. 同一 job 内若多次运行 profiling，当前 `profile/manifest.json` 与 `profile/profile.json` 可以代表最新一轮，但必须在 `jobs/{SESSION_ID}/.meta/artifact_index.json` 中写清它们对应的输入 CSV、产生时间与本轮用途。
3. 若本轮 profiling 是为追加分析服务，必须同时更新 `jobs/{SESSION_ID}/.meta/analysis_journal.md`，说明这轮画像支撑了什么分析。
4. 当存在多个成功导出 CSV 时，必须显式传 `--data-csv`，不要让 profile 与错误文件绑定。

## 脚本化建议（推荐）

连续分析场景下，推荐使用 wrapper，把 profiling 产物与输入 CSV 的绑定关系回写进 `artifact_index.json`：

```bash
./scripts/py skills/data-profile/scripts/profiling_with_meta.py --session-id $SESSION_ID
./scripts/py skills/data-profile/scripts/profiling_with_meta.py --session-id $SESSION_ID --data-csv jobs/$SESSION_ID/data/<正式CSV文件名>
```

（仅排障时才直接调用 `skills/data-profile/scripts/run.py`）

## 示例

```bash
python3 {baseDir}/skills/data-profile/scripts/run.py
python3 {baseDir}/skills/data-profile/scripts/run.py --data-csv jobs/job_001/data/交叉_销售_2025Q1.csv --output-dir jobs/job_001
python3 {baseDir}/skills/data-profile/scripts/profile.py jobs/job_001/data/交叉_销售_2025Q1.csv jobs/job_001
```

---

## 语义类型识别

Profiling 会自动识别以下语义类型（用于格式化）：

| 语义类型 | 识别规则 | 格式化效果 |
|----------|----------|------------|
| `percentage` | 列名含"率/比/占比"，或值在 0-1/0-100 | `85.3%` |
| `money` | 列名含"价格/金额/收入/客单价"，或保留2位小数 | `¥1,234.5` |
| `count` | 整数 + 列名含"数/量/次数" | `12,345` |
| `delta` | 列名含"同比/环比/增长/变化" | `12.3` |
| `float` | 浮点数 | `123.4` |

**识别结果存储在**：`profile/manifest.json` 的 `schema.columns[].semantic_type`

**后续使用**：Report-writing skill 的 `format_utils` 会读取此字段进行格式化。

## 大文件处理

大文件处理规则已下沉到 `{baseDir}/skills/data-profile/references/large-file-rules.md`。执行时遵循以下最小顺序：

1. 优先运行 `run.py`；仅在需要手工指定输入时才直接运行 `profile.py`
2. 默认正式 CSV 识别顺序为：`export_summary.json` → `duckdb_export_summary.json` → 显式 `--data-csv`
3. 需要样本时，再用 `head` / `grep` / 采样读取必要片段
4. 禁止对大 CSV 做全量 `read`

## 输出优先级

按以下顺序使用画像结果：

1. `schema` 与语义类型
2. 行数、列数、缺失率、Top 值分布
3. 必要时再补充少量样本行
