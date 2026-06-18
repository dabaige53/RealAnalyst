# 分析框架网络调研摘要

## 目标

补齐 RealAnalyst 的“分析框架层”：先决定用什么工具拆问题，再选择报告模板，而不是每次都退回单一假设树。

## 可复用来源

1. Issue Tree / MECE
   - 来源：Wikipedia 的 issue tree 与 MECE principle 条目，说明 issue tree 用于把关键问题分解为诊断树或方案树，分支应互斥且穷尽。
   - URL: https://en.wikipedia.org/wiki/Issue_tree
   - URL: https://en.wikipedia.org/wiki/MECE_principle
   - 落地：用于 overview / structure / scope 问题，解决“不重不漏地拆总量、结构、维度”的规划。

2. Waterfall / Bridge
   - 来源：waterfall chart 条目说明它用于理解连续正负变化对总量的累积影响，常用于收入、利润、预算差异解释。
   - URL: https://en.wikipedia.org/wiki/Waterfall_chart
   - 落地：用于 attribution / variance 问题，解决“变化来自哪些驱动因素”的规划。

3. Goals-Signals-Metrics / HEART
   - 来源：Google Research 的 HEART paper 摘要说明框架把产品目标映射为可度量指标，用于支持产品决策。
   - URL: https://research.google/pubs/measuring-the-user-experience-on-a-large-scale-user-centered-metrics-for-web-applications/
   - 落地：用于 metric planning / product health / dashboard 设计，解决“先定义目标，再找信号和指标”的规划。

4. Funnel analysis
   - 来源：funnel analysis 条目说明漏斗分析用于映射一串事件到目标行为，并计算步骤转化率。
   - URL: https://en.wikipedia.org/wiki/Funnel_analysis
   - 落地：用于 conversion / process / journey 问题，解决“在哪一步流失或转化”的规划。

5. Root Cause / 5 Whys / Ishikawa
   - 来源：root-cause analysis 和 five whys 条目说明 RCA 用于识别问题根因，5 Whys 通过连续追问因果链探索根因，但也有过浅和不可复现风险。
   - URL: https://en.wikipedia.org/wiki/Root-cause_analysis
   - URL: https://en.wikipedia.org/wiki/Five_whys
   - 落地：用于 incident / anomaly / recurring issue 问题，要求用数据证据约束根因假设，避免只靠主观追问。

6. Radar / Benchmark
   - 来源：radar chart 条目说明雷达图用于展示多变量对象对比，但也提示其在变量尺度、面积感知和样本过多时有误导风险。
   - URL: https://en.wikipedia.org/wiki/Radar_chart
   - 落地：用于 benchmark / profile comparison / capability gap 问题；输出时默认优先表格或条形图，雷达图只是可选呈现。

## 项目内取舍

* 不把所有框架都等同为报告模板；framework 决定分析拆解，report template 决定呈现。
* 保留 MECE / Waterfall / Radar 等常用英文名作为 alias，但正式框架 ID 应更贴近分析动作：`mece_issue_tree`、`waterfall_attribution`、`gsm_metric_planning`、`funnel_conversion`、`root_cause`、`benchmark_radar`。
* 每个框架必须写清：
  - 适用问题
  - 不适用问题
  - logic_path
  - goal_template
  - evidence_requirements
  - recommended_templates
  - failure_modes
* 这样可以解决“所有分析都像假设模板”的问题：不同问题会先进入不同 framework，再生成不同目标和证据链。
