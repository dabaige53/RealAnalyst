# Report Skill

把分析结果写成用户能读、能复核、能追溯的数据报告。

---

## 什么时候用？

- analysis-plan 已锁定模板
- 数据画像和分析结果已形成
- 需要追加同一 job 的后续分析
- 需要输出文件清单和口径说明

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | analysis_plan.md<br/>acquisition_log<br/>artifact_index<br/>analysis_journal<br/>profile<br/>分析结果 |
| 输出 | 报告 Markdown<br/>输出文件清单<br/>需求时间线<br/>报告更新时间线 |
| 下一步 | `RA:report-verify` |

---

## 流程图

```mermaid
flowchart LR
    Plan[已锁模板] --> Evidence[读取证据] --> Draft[写报告] --> Files[输出文件清单] --> Append[同 job 追加]
```

---

## 快速示例

```bash
/skill RA:report
基于当前 job 的 plan、profile 和分析结果写报告。
```

---

## 用户会得到什么？

- 一份可交付的 Markdown 报告。
- 数据来源、指标口径、限制和输出文件清单。
- 每条结论对应的关键数字和证据说明。
- 需要人工复核的问题列表。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `RA:analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 检查 plan、profile、artifact index 是否来自同一个 job |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
