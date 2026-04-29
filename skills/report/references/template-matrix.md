# 报告模板选择矩阵（核心模板版）

本页只回答一件事：**这次应该从 6 个核心模板里选哪一个。**

## 先看分析模式，再看交付方式

| analysis_mode | delivery_mode | 优先模板 | 备用模板 |
| --- | --- | --- | --- |
| `overview` | `executive_brief` | `executive_onepage` | — |
| `overview` | `structured_report` | `summary_structured` | `technical_detailed` |
| `ranking` | `executive_brief` | `executive_onepage` | `ranking_report` |
| `ranking` | `structured_report` | `ranking_report` | `summary_structured` |
| `attribution` | `executive_brief` | `executive_onepage` | `attribution_report` |
| `attribution` | `diagnosis_report` | `attribution_report` | — |
| `benchmark` | `executive_brief` | `executive_onepage` | `competitor_compare` |
| `benchmark` | `structured_report` | `competitor_compare` | `summary_structured` |
| `benchmark` | `diagnosis_report` | `competitor_compare` | — |
| `exploration` | `structured_report` | `summary_structured` | `technical_detailed` |
| `exploration` | `detailed_report` | `technical_detailed` | — |

## 周期类请求怎么处理

| 用户说法 | 不要怎么做 | 应该怎么做 |
| --- | --- | --- |
| 日报 | 不要直接锁 `daily_monitor` | 识别问题后，一般落到 `executive_onepage` |
| 周报 / 月报 / 季报 / 年报 | 不要直接锁旧周期模板 ID | 先判断 analysis_mode / delivery_mode，通常落到 `summary_structured` |

## 旧模板名怎么处理

若用户或历史文档出现这些名字：

- `daily_monitor`
- `weekly_summary`
- `monthly_analysis`
- `quarterly_review`
- `yearly_report`
- `market_overview`
- `route_deep_dive`
- `anomaly_alert`
- `trend_analysis`
- `structure_insight`
- `dashboard_summary`
- `problem_oriented`

统一视为 **alias / preset**，不要再把它们当成主模板维护。

## 使用规则

1. 优先锁定核心模板 ID。
2. 如果 plan 里出现旧模板 ID，先通过 `template_aliases` 解析 `canonical_template`。
3. 若 `selected_analysis_mode`、`selected_delivery_mode`、`selected_report_template` 三者不匹配，应回到 planning 修正。
4. 不得在写报告阶段重新发明新模板或临时恢复旧模板为主模板。
