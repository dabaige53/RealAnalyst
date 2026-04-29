# Analysis Run Skill

RealAnalyst 的总控工作流，负责从需求理解、用户确认、取数、画像、分析、写报告到验证的完整链路。

---

## 什么时候用？

- 用户提出一个完整分析任务
- 需要连续追问和同一 job 追加报告
- 需要先确认方案再执行
- 需要统一管理数据、报告、元数据留痕

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 用户问题<br/>metadata context<br/>analysis_plan.md<br/>runtime registry |
| 输出 | jobs/{SESSION_ID}/<br/>正式 CSV<br/>profile<br/>analysis_journal<br/>报告<br/>verification.json |
| 下一步 | `RA:report / RA:report-verify` |

---

## 流程图

```mermaid
flowchart LR
    Ask[需求理解] --> Confirm[用户确认] --> Export[受控取数] --> Profile[数据画像] --> Analyze[分析] --> Report[追加报告] --> Verify[验证]
```

---

## 快速示例

```bash
/skill RA:analysis-run
帮我基于现有 metadata 生成计划，确认后执行取数、画像、分析和报告。
```

---

## 用户会得到什么？

- 一个完整 job 目录。
- 已确认的分析计划、导出数据、画像结果和报告。
- 本次分析使用了哪些数据、哪些口径、哪些文件。
- 交付前验证结果和需要人工复核的风险点。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `RA:analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 先检查当前 job 是否混入了旧数据或旧计划 |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
