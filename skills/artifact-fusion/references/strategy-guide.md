# Fusion Strategy Guide

`fusion.py` 提供三种合并策略，以及 `--join-key` 键 join 支持。

## 策略选择

| 策略 | 适用场景 | 实现 |
|---|---|---|
| `union` | 多数据集 schema 相同，需纵向拼接（行追加） | `pd.concat(ignore_index=True)` |
| `join` | 多数据集需横向合并，按**业务键**关联 | `pd.merge(on=key, how='left')` |
| `join`（不传 key） | 同源同序数据，按索引（行号）拼列 | `pd.concat(axis=1)` |
| `passthrough` | 单数据集，只更新 manifest 血缘信息 | 返回第一个文件 |

## join 策略详解

### 键 join（推荐）

传入 `--join-key` 时，使用 `pd.merge(on=key, how='left')`：

```bash
python3 {baseDir}/skills/artifact-fusion/scripts/fusion.py join \
  {baseDir}/jobs/job_001/merged \
  {baseDir}/jobs/job_001/ds_a \
  {baseDir}/jobs/job_001/ds_b \
  --join-key "产品"
```

- 保留左表（ds_a）所有行
- 按 `产品` 字段与右表（ds_b）关联
- 同名非键列自动加后缀 `_left` / `_right`

### 索引 join（仅限同源同序）

不传 `--join-key` 时，使用 `pd.concat(axis=1)` 按行号拼列：

```bash
python3 {baseDir}/skills/artifact-fusion/scripts/fusion.py join \
  {baseDir}/jobs/job_001/merged \
  {baseDir}/jobs/job_001/ds_a \
  {baseDir}/jobs/job_001/ds_b
```

⚠️ **仅适用于**：两表行顺序一致（同源同序数据）。若行序不一致会产生静默错误。

## union 策略详解

```
dataset_a: [col1, col2, col3] 100 rows
dataset_b: [col1, col2, col3] 200 rows
→ merged:  [col1, col2, col3] 300 rows（列并集，缺失填 NaN）
```

## 人工校验步骤

### 行数检查

```bash
wc -l data1.csv data2.csv data_merged.csv
# union: merged 行数 ≈ data1 + data2
# join: merged 行数取决于键匹配
# passthrough: merged 行数 = data1
```

### 列数检查

```bash
head -1 data_merged.csv | tr ',' '\n' | wc -l
# union: 列数 = data1 ∪ data2
# join (键): 列数 = data1 + data2 - 1 (共享键)
# passthrough: 列数 = data1
```

### 关键字段存在性检查

```bash
head -1 data_merged.csv | grep "关键字段名"
head -10 data_merged.csv | cut -d',' -f<列号>
```

### 完整校验脚本

```bash
#!/bin/bash
echo "=== 行数检查 ==="
echo "data1: $(wc -l < data1.csv) 行"
echo "data2: $(wc -l < data2.csv) 行"
echo "merged: $(wc -l < data_merged.csv) 行"

echo "=== 列数检查 ==="
echo "merged: $(head -1 data_merged.csv | tr ',' '\n' | wc -l) 列"

echo "=== 数据预览 ==="
head -5 data_merged.csv

echo "=== 空行检查 ==="
empty_lines=$(awk -F',' 'NF==1' data_merged.csv | wc -l)
echo "空行数: $empty_lines"
```

## 前置条件

- `union` / `join`：至少需要两个已完成的 `RA:data-export` 产物
- `passthrough`：至少需要一个产物
- 每个输入目录必须包含有效的 CSV 和 `export_summary.json` / `duckdb_export_summary.json`
- fusion 后必须重新运行 `RA:data-profile`
