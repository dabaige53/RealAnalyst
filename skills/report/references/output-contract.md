# 输出契约

本页定义报告产物的路径、命名、导出阈值和清单格式。所有输出都必须写入 `jobs/{SESSION_ID}/`。

## 真源分层

1. **执行状态真源**：`logs/<job_id>/status.json`
2. **取证真源**：`logs/<job_id>/events.jsonl` 与 OpenCode storage
3. **用户态产物真源**：`outputs/<job_id>/artifact_index.json`
4. `profile/manifest.json` 仅用于 profiling 与格式化，不是用户态产物真源
5. generic `profile/assertions.json` 不可作为用户态审计真源

`artifact_index.json` 用于统一描述：

- 最终报告文件
- 正式附件列表
- 导出条目与参数
- 验证文件路径
- 用户态审计摘要

当前用户态附件清单只应包含：

- 报告文件（`报告_*.md` / `report.md`）
- 顶层分析产物（写在任务根目录的 `汇总_*.csv`、`交叉_*.csv` 等 CSV）
- 可选 `verification.json`

当运行中尚未 finalize 到 `outputs/<job_id>/` 时，允许临时读取 `jobs/{SESSION_ID}/export_summary.json` 与 `profile/manifest.json` 作为生成报告的输入，但报告写作完成后，对外展示和邮件附件的用户态口径必须收敛到 `artifact_index.json`。

## 目录与依赖

```text
jobs/{SESSION_ID}/
├── .meta/analysis_plan.md
├── profile/manifest.json
├── profile/profile.json
├── 报告_{主题}_{时间}.md
├── 汇总_{维度}_{时间}_{筛选}.csv
└── 交叉_{维度A}×{维度B}_{时间}_{筛选}.csv
```

写报告前必须读取：

- `jobs/{SESSION_ID}/.meta/analysis_plan.md`
- `jobs/{SESSION_ID}/profile/manifest.json`
- `jobs/{SESSION_ID}/profile/profile.json`

## 中文命名与 plan 契约优先

1. 报告文件名固定为 `报告_{主题}_{时间}.md`。
2. 所有文件名元素必须使用中文，交叉表使用 `×`，不要用 `x` 或 `-` 代替。
3. 文件名必须与 `analysis_plan.md` 中的 `filename` 保持一致。
4. 当 plan 明确指定 `artifact: csv` 时，无论行数多少都必须导出独立 CSV。

示例：

```markdown
- [ ] goal-dim-代理人: 按代理人维度分析结构分布
  - artifact: csv
  - filename: 汇总_代理人_2025Q4.csv
  - params: { top_n: 20 }
```

## 行数阈值与导出决策

| 数据类型 | 行数阈值 | 默认处理方式 | 说明 |
| --- | --- | --- | --- |
| 时间趋势汇总表 | ≤ 12 行 | 嵌入报告 | 直接写成 Markdown 表格 |
| 交叉分析表 | ≤ 20 行 | 嵌入报告 | 直接写成 Markdown 表格 |
| 交叉分析表 | > 20 行 | 独立 CSV | Top N×M 嵌入报告，完整数据存 CSV |
| 排名汇总表 | ≤ 50 行 | 嵌入报告 | 完整表格嵌入报告 |
| 排名汇总表 | > 50 行 | 独立 CSV | 报告展示 Top N，CSV 保留全量 |

排名类输出额外规则：

1. 导出 CSV 时保留全量数据，不在导出阶段截断。
2. `params.top_n` 只控制报告展示层，不控制 CSV 导出层。
3. 当 plan 已指定 `artifact: csv` 时，plan 契约优先于默认阈值。

## CSV 格式化与列名

1. 所有输出 CSV 的列名必须映射回中文，不能保留英文列名。
2. 所有输出 CSV 都必须基于 `jobs/{SESSION_ID}/profile/manifest.json` 做格式化。
3. 百分比、货币、小数、整数统一采用项目约定格式。

示例：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("{baseDir}") / "lib"))
from format_utils import format_csv

format_csv("汇总_产品排名_2025Q4.csv", "jobs/{SESSION_ID}/profile/manifest.json")
```

## 数据来源章节

1. 报告前部必须包含 `## 数据来源`。
2. `## 数据来源` 只保留来源元信息：Tableau 原始名称、页面 URL、筛选条件、备注。
3. 禁止在头部或正文手写全量本地文件清单；文件名统一交给系统扫描后追加到报告末尾。
4. 数据源名称必须中文化，同时保留 Tableau 原始名称与 URL。
5. 运行中撰写报告时，来源元信息可从 `export_summary.json`、`profile/manifest*.json`、`.meta/analysis_plan.md` 获取；对外的最终用户态来源口径必须以 `artifact_index.json` 为准。

## 输出文件清单

报告末尾必须包含 `## 输出文件清单`，但该章节由系统在报告文件写入后自动追加。AI 不得在正文中预写、猜写或重复枚举文件名。

系统追加规则：

```bash
ls -1 jobs/{SESSION_ID}/*.csv jobs/{SESSION_ID}/*.md 2>/dev/null
```

清单规则：

1. 必须遍历目录后生成，不能靠 AI 猜测手写。
2. 必须列出全部分析产物，不可遗漏任何 `汇总_*.csv`、`交叉_*.csv`、`报告_*.md`。
3. `data/` 下原始数据不得出现在 `### 分析产物(已附邮件)`，如需保留存档路径，只能放在 `### 原始数据(仅存档)`。
4. `profile/` 下画像文件、`*.flag`、`*.txt` 状态文件不进入任何清单小节。
5. `export_summary.json`、`artifact_index.json`、根目录 `manifest.json` 属于系统/审计文件，不进入任何用户态附件清单。
6. 推荐使用分类清单格式，便于兼容模块识别附件；正式对外交付以 `artifact_index.json` 为主。

推荐格式：

```markdown
## 输出文件清单

### 分析产物(已附邮件)
- 报告_上海区域代理人销售分析_2025Q4.md
- 汇总_代理人_2025Q4.csv
- 交叉_月份×代理人_2025Q4.csv

### 原始数据(仅存档)
- data/data.csv
```
