# File Path Specification

## 唯一工作目录规则

1. **唯一工作目录**：所有输出必须写入 `jobs/{SESSION_ID}/`。
2. **单会话只允许一个 job**：同一会话后续追问、补数、补分析、补报告，都继续使用同一个 `jobs/{SESSION_ID}/`。
3. **禁止自创第二个会话级 job 目录**：严禁在同一会话里再创建新的 job 目录。
4. **SESSION_ID 来源**：从 Prompt 头部 `[session:xxx]` 提取。
5. **报告文件复用**：首轮创建报告文件；后续轮次继续更新同一路径，不重写新的主报告文件。
6. **元数据文件必须保留**：至少维护 `.meta/analysis_plan.md`、`.meta/normalized_request.json`、`.meta/acquisition_log.jsonl`、`.meta/artifact_index.json`、`.meta/analysis_journal.md`、`.meta/user_request_timeline.md`、`.meta/metadata_feedback.jsonl`。

## Job 目录结构

```
jobs/{SESSION_ID}/
├── data/                         # 数据文件（tableau 导出或 duckdb 落盘结果）
├── profile/                      # 数据画像（profiling skill 自动创建）
├── .meta/
│   ├── analysis_plan.md          # 分析计划
│   ├── normalized_request.json   # 需求归一化结果
│   ├── acquisition_log.jsonl     # 每次下载动作留痕
│   ├── artifact_index.json       # job 内正式产物索引
│   ├── analysis_journal.md       # 每轮分析日志
│   ├── user_request_timeline.md  # 用户需求时间线
│   └── metadata_feedback.jsonl   # metadata 问题线索，只供 refine 使用
├── analysis.json                  # 结构化分析结果（RA:report-verify 正式输入）
├── 报告_{主题}_{时间}.md          # 首版报告；后续轮次持续追加更新
└── 汇总_*.csv / 交叉_*.csv        # 分析产出
```
