---
name: "RA:artifact-fusion"
description: |
  Merge multiple datasets into unified data with lineage tracking. Use when: (1) Combine datasets 
  from different sources, (2) Union datasets with same schema, (3) Join datasets on common keys, 
  (4) Pass through single dataset with manifest update.
  Triggers: fusion, 数据融合, 合并, merge, join, union, 数据合并.
---

# Fusion Skill

将多个 Dataset Pack 合并为单一数据集，并生成统一 manifest。

## 什么时候该用？

| 场景 | 说明 |
|------|------|
| 多 source 同 schema 合并 | 多个 Tableau 视图或 DuckDB 表结构相同，需要纵向拼接（`union`） |
| 补充维表 join | 主表需要关联参考维度表的字段（`join`）；**注意：当前 join 是按索引拼列，非键 join** |
| 单 source 通行 | 只有一个输入但需要统一 manifest 格式（`passthrough`） |

### 前置条件

- 必须先有 **两个以上已完成的 `RA:data-export` 产物**（`union`/`join`），或至少一个（`passthrough`）。
- 每个输入目录必须包含有效的 CSV 和 `export_summary.json` / `duckdb_export_summary.json`。

### 从 analysis-run 进入 fusion 的路径

1. `RA:analysis-run` Phase 3 发现当前数据不足以回答问题，需要引入新数据源。
2. 用户确认新增数据源后，`RA:data-export` 完成第二次导出。
3. 此时可调用 `RA:artifact-fusion` 将两次导出产物合并。
4. 合并后的数据送入 `RA:data-profile` 做画像，再继续分析。

> `RA:analysis-run` 默认不做静默拼接。只有在用户明确要求合并、且有多个已完成的导出产物时，才触发 fusion。

## 用法

```bash
python3 {baseDir}/skills/artifact-fusion/scripts/fusion.py <strategy> <output_dir> <input_dir1> [input_dir2] ...
```

## 参数

| 参数 | 说明 |
|------|------|
| `strategy` | 合并策略: `union` / `join` / `passthrough` |
| `output_dir` | 输出目录 |
| `input_dir*` | 输入目录 (包含 manifest.json + data.csv) |

## 策略详解

### passthrough - 单数据集透传

| 条件 | 只有 1 个数据集 |
|------|----------------|
| 操作 | 直接复制数据，更新 manifest 血缘信息 |

### union - 垂直合并（行拼接）

| 条件 | 多数据集，schema 相同 |
|------|----------------------|
| 操作 | 按行追加所有数据 |
| 要求 | 列名和列数必须一致 |

```
dataset_a: [col1, col2, col3] 100 rows
dataset_b: [col1, col2, col3] 200 rows
→ merged: [col1, col2, col3] 300 rows
```

### join - 水平合并（列拼接）

| 条件 | 多数据集，有共同键 |
|------|-------------------|
| 操作 | 基于共同键进行 left join |
| 默认 | left join（保留左表所有行） |

**共同键识别规则**：

1. 优先使用名称完全匹配的列
2. 其次使用业务键（如：产品、代理人、日期）
3. 如无法识别，报错退出

**列名冲突处理**：

- 同名列自动添加后缀：`_left`, `_right`
- 例如：`客单价` → `客单价_left`, `客单价_right`

## 输出文件

### data.csv - 合并后数据

合并后的完整数据集。

### manifest.json - 带血缘的元数据

```json
{
  "source": "fusion",
  "strategy": "union",
  "row_count": 300,
  "columns": ["产品", "人数", "客单价"],
  "lineage": {
    "inputs": [
      {
        "path": "jobs/job_001/ds_a",
        "source_key": "sales.ai_",
        "row_count": 100
      },
      {
        "path": "jobs/job_001/ds_b",
        "source_key": "sales.ai_market",
        "row_count": 200
      }
    ],
    "merged_at": "2025-01-17T10:30:00Z"
  }
}
```

## 示例

```bash
# 多数据集 join
python3 {baseDir}/skills/artifact-fusion/scripts/fusion.py join {baseDir}/jobs/job_001/merged {baseDir}/jobs/job_001/ds_a {baseDir}/jobs/job_001/ds_b
```

---

## 融合后校验建议

**⚠️ 重要说明**：以下是**人工校验建议**（非脚本自动化）

### fusion 策略说明

`fusion.py` 提供 3 种策略：

| 策略 | 实现 | 说明 |
|------|------|------|
| `union` | `pd.concat(ignore_index=True)` | concat 行，列并集，缺失填 NaN |
| `join` | `pd.concat(axis=1)` | **按索引（行号）拼列，非键 join** |
| `passthrough` | 返回第一个文件 | 直接返回，不融合 |

### 人工校验步骤

#### 1. 行数检查

```bash
wc -l data1.csv data2.csv data_merged.csv

# 预期：
# union: merged 行数 ≈ data1 + data2（忽略表头重复）
# join: merged 行数取决于索引对齐
# passthrough: merged 行数 = data1
```

#### 2. 列数检查

```bash
head -1 data_merged.csv | tr ',' '\n' | wc -l

# 预期：
# union: 列数 = data1 ∪ data2（列并集）
# join: 列数 = data1 + data2
# passthrough: 列数 = data1
```

#### 3. 关键字段存在性检查

```bash
# 检查关键字段是否在表头中
head -1 data_merged.csv | grep "关键字段名"

# 检查字段是否有数据
head -10 data_merged.csv | cut -d',' -f<列号>
```

#### 4. 数据完整性抽查

```bash
# 随机抽查几行，确认无明显异常
head -20 data_merged.csv
tail -20 data_merged.csv

# 检查是否有完全为空的行
awk -F',' 'NF==1' data_merged.csv
```

### 对 join 模式的特殊警告

**⚠️ join 是按索引（行号）拼列，不是按键 join**

**索引对齐前提**：
- 两表的行顺序必须一致
- 如果任何一侧排序/过滤不同步， join 会产生"看似成功、实则错配"的静默错误

**join 模式仅适用于**：
- 同源同序数据
- 已证明行序一致（例如基于某个稳定字段的逐行 hash 对比）

**如果需要按键合并**：
1. 先对两个文件按键排序
2. 确保行号对齐
3. 再使用 join 模式

或者使用外部工具（如 pandas 脚本）进行键 join。

### 校验脚本示例

```bash
#!/bin/bash
# fusion 后校验脚本

echo "=== 行数检查 ==="
echo "data1: $(wc -l < data1.csv) 行"
echo "data2: $(wc -l < data2.csv) 行"
echo "merged: $(wc -l < data_merged.csv) 行"

echo "\n=== 列数检查 ==="
echo "data1: $(head -1 data1.csv | tr ',' '\n' | wc -l) 列"
echo "data2: $(head -1 data2.csv | tr ',' '\n' | wc -l) 列"
echo "merged: $(head -1 data_merged.csv | tr ',' '\n' | wc -l) 列"

echo "\n=== 数据预览 ==="
head -5 data_merged.csv

echo "\n=== 空行检查 ==="
empty_lines=$(awk -F',' 'NF==1' data_merged.csv | wc -l)
echo "空行数: $empty_lines"
```

## Completion Summary

融合完成后，向用户汇报：

1. 使用了哪种策略（union / join / passthrough）。
2. 合并了哪些输入（路径和行数）。
3. 输出 `data.csv` 行数和列数。
4. `manifest.json` 已生成，包含 lineage 信息。
5. 下一步建议：进入 `/skill RA:data-profile` 对合并后数据做画像。
