# 大文件处理规则

本页是 profiling 相关的大文件读取与 token 控制规则。

## 禁止操作

| 文件大小 | 禁止操作 | 原因 |
| --- | --- | --- |
| > 1MB | 使用 `read` 工具读取全量内容 | Token 爆炸（1MB ≈ 250K tokens） |
| > 1MB | 多次读取同一文件 | 累积 Token 消耗 |
| 任意大小 | 把大量内容复制进对话 | 超出上下文窗口 |

## 推荐顺序

1. 优先运行 `python3 {baseDir}/skills/data-profile/scripts/run.py`
2. 仅在自动解析不到正式 CSV 时，再运行 `python3 {baseDir}/skills/data-profile/scripts/profile.py <data_csv> <output_dir>`
3. 只读取 `profile/profile.json` 与 `profile/manifest.json`
4. 需要样本时，用 `head` / `grep` / 采样读取局部内容

## 常用命令

```bash
head -20 data.csv
(head -1 data.csv && grep "<关键词>" data.csv) > data_filtered.csv
wc -l data_filtered.csv && head -3 data_filtered.csv
cut -d',' -f3 data.csv | sort | uniq -c | sort -rn | head -20
```

## 失败切换策略

| 失败方法 | 切换到 |
| --- | --- |
| awk 筛选失败 | grep 关键词匹配 |
| 复杂正则失败 | 简单字符串匹配 |
| 全量处理失败 | 采样处理 |

## 采样策略

```bash
shuf -n 1000 data.csv > sample.csv
awk 'NR==1 || NR%10==0' data.csv > sample.csv
```

## 输出优先级

1. Schema / 列统计
2. 缺失与异常分布
3. 样本数据（最多 50 行）
