# 分析框架库

本文件说明 `analysis-frameworks.json` 的使用方式。框架库回答的是“这次分析应该怎样拆问题”，不是“最终报告长什么样”。报告模板仍由 `skills/report/references/template-system-v2.md` 负责。

## 选择顺序

1. 先识别业务问题类型：总览、归因、转化、留存、根因、对标、指标规划。
2. 再选择分析框架：例如 `mece_issue_tree`、`waterfall_attribution`、`funnel_conversion`。
3. 再锁定交付方式：`executive_brief`、`structured_report`、`diagnosis_report`、`detailed_report`。
4. 最后映射核心报告模板：如 `summary_structured`、`attribution_report`、`competitor_compare`。

## 核心框架

| 框架 ID | 常用别名 | 解决的问题 | 默认报告模板 |
| --- | --- | --- | --- |
| `mece_issue_tree` | MECE, issue tree | 宽泛问题如何不重不漏地拆结构 | `summary_structured` |
| `waterfall_attribution` | Waterfall, bridge | 指标变化由哪些因素贡献 | `attribution_report` |
| `gsm_metric_planning` | GSM, OSM, HEART | 模糊目标如何转成信号和指标 | `summary_structured` |
| `funnel_conversion` | funnel | 流程或用户旅程在哪一步流失 | `attribution_report` |
| `cohort_retention` | cohort, retention | 不同队列后续表现如何变化 | `summary_structured` |
| `root_cause` | RCA, 5 Whys, fishbone | 已发生问题的可干预根因是什么 | `attribution_report` |
| `benchmark_radar` | benchmark, radar | 多对象多指标差距和短板是什么 | `competitor_compare` |

## Planning 使用规则

- `RA:analysis-plan` 必须先查询框架，再生成目标和假设：

```bash
python3 {baseDir}/skills/analysis-reference/scripts/query_config.py --framework <framework_or_alias>
```

- 命中结果中的 `logic_path` 决定下钻顺序。
- `goal_template` 决定 plan 中固定目标、维度目标和假设验证目标的写法。
- `evidence_requirements` 决定报告正文必须直接展示哪些证据块。
- `recommended_templates` 只给模板映射建议，不替代 report template 真源。

## 解决“单一分析方向”的规则

不要所有分析都从同一套假设树开始。先按问题形态分流：

| 用户问题 | 应优先选 |
| --- | --- |
| “整体情况怎么样？” | `mece_issue_tree` |
| “为什么下降/上涨？” | `waterfall_attribution` |
| “指标体系/看板怎么设计？” | `gsm_metric_planning` |
| “哪一步转化掉了？” | `funnel_conversion` |
| “不同批次后续表现如何？” | `cohort_retention` |
| “这个异常根因是什么？” | `root_cause` |
| “和竞品/目标差在哪？” | `benchmark_radar` |

如果用户问题同时命中多个框架，优先选择最贴近业务决策的主框架，其它框架只能作为辅助目标，不要把多个框架平铺进同一份 plan。

## 来源说明

框架内容参考公开方法论并按 RealAnalyst 的计划、取数、画像、报告链路重写为可执行配置。主要来源包括 Issue Tree / MECE、Waterfall chart、Google HEART / Goals-Signals-Metrics、Funnel analysis、Cohort analysis、Root Cause Analysis、Five Whys 和 Radar chart。具体 URL 保存在 `analysis-frameworks.json` 的 `sources` 字段。
