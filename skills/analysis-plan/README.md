# Analysis Plan Skill

把用户问题和 metadata context 转成正式分析计划，锁定业务假设、数据源、指标、维度、分析路径和报告模板。

---

## 什么时候用？

- 正式取数前
- 需要确认分析方法
- 需要把用户问题拆成可执行目标
- 需要生成 .meta/analysis_plan.md

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 用户问题<br/>normalized_request.json<br/>metadata context pack<br/>runtime 查询结果 |
| 输出 | jobs/{SESSION_ID}/.meta/analysis_plan.md<br/>业务假设<br/>分析目标<br/>模板选择<br/>风险与限制 |
| 下一步 | `RA:analysis-run` |

---

## 流程图

```mermaid
flowchart LR
    Request[用户问题] --> Context[metadata context] --> Hypothesis[业务假设] --> Goals[分析目标] --> Template[报告模板] --> Plan[analysis_plan.md]
```

---

## 快速示例

```bash
/skill RA:analysis-plan
基于 metadata context，为这个问题生成分析计划。
```

---

## 用户会得到什么？

- 一份可确认的分析计划。
- 本次要回答的问题、指标、维度和数据源。
- 需要先确认的口径、权限或数据限制。
- 建议使用的报告结构和下一步取数动作。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `RA:analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 回到用户问题和 metadata context，确认目标是否已经说清楚 |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
