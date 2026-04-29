# 模板体系 2.1：6 个核心模板 + alias / preset

## 核心原则

- 模板是**交付护栏**，不是分析方向盘。
- 先定问题类型，再定分析模式，再定交付方式，最后才落到具体模板。
- 正式 planning 默认只锁定**核心模板 ID**。
- 旧模板名（日报、月报、问题导向、仪表盘摘要等）保留为 `template_aliases`，只用于迁移和查询，不再作为主模板维护。

## 当前核心模板

| 核心模板 | 主要用途 | analysis_mode | delivery_mode |
| --- | --- | --- | --- |
| `executive_onepage` | 高层快速汇报、异常快报、单屏摘要 | overview / ranking / attribution / benchmark | executive_brief |
| `summary_structured` | 常规正式报告、综合分析、专题结构化汇报 | overview / exploration | structured_report |
| `ranking_report` | Top/Bottom、头尾部差距 | ranking | structured_report |
| `attribution_report` | 原因分析、变化归因、问题诊断 | attribution | diagnosis_report |
| `competitor_compare` | 竞品/目标对标、市场差距 | benchmark | structured_report / diagnosis_report |
| `technical_detailed` | 方法说明多、明细多、附录重 | exploration | detailed_report |

## 已压缩掉的旧模板（现在都是 alias / preset）

| 旧模板 | 现状 | 归并到 |
| --- | --- | --- |
| `daily_monitor` | 周期 preset | `executive_onepage` |
| `weekly_summary` | 周期 preset | `summary_structured` |
| `monthly_analysis` | 周期 preset | `summary_structured` |
| `quarterly_review` | 周期 preset | `summary_structured` |
| `yearly_report` | 周期 preset | `summary_structured` |
| `market_overview` | 主题 alias | `competitor_compare` |
| `route_deep_dive` | 主题 alias | `summary_structured` |
| `anomaly_alert` | 场景 alias | `executive_onepage` |
| `trend_analysis` | 分析块 alias | `summary_structured` |
| `structure_insight` | 分析块 alias | `summary_structured` |
| `dashboard_summary` | 呈现 alias | `executive_onepage` |
| `problem_oriented` | 诊断 alias | `attribution_report` |

## 选择顺序

1. 识别 `request_type`
2. 锁定 `selected_analysis_mode`
3. 锁定 `selected_delivery_mode`
4. 从 6 个核心模板中选择 `selected_report_template`
5. 若用户明确说旧模板名，只把它当作 alias 线索，最终仍落到核心模板 ID

## alias 的正确用法

- 用户说“出个月报” → 先识别是不是 `overview + structured_report`，最终锁 `summary_structured`
- 用户说“做个异常预警” → 先识别是不是 `attribution + executive_brief`，最终锁 `executive_onepage`
- 用户说“做问题导向报告” → 先识别是不是 `attribution + diagnosis_report`，最终锁 `attribution_report`

## planning 约束

plan 中至少写：

- `selected_analysis_mode`
- `analysis_mode_selection_reason`
- `selected_delivery_mode`
- `delivery_mode_selection_reason`
- `selected_report_template`  ← **这里默认写核心模板 ID**
- `template_selection_reason`

## writing 约束

- 写报告时优先按核心模板执行。
- 若历史 plan 或人工输入用了旧模板 ID，先查 `template_aliases`，解析成 `canonical_template`，再执行。
- alias 只解决迁移与兼容，不允许重新膨胀回 18 个主模板。
