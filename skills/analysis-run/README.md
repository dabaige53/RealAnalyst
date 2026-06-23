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
| 输出 | jobs/{SESSION_ID}/<br/>job_manifest.json<br/>正式 CSV<br/>profile<br/>analysis_journal<br/>报告<br/>verification.json |
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

- 一次可追溯的分析交付。
- 一份统一的内部记录，保存可见交付物、内部证据、验证和归档状态。
- 默认用户回复只展示业务摘要、可查看交付物、验证结果和下一步；内部路径和过程文件留在 manifest 里。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `RA:analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 先检查当前 job 是否混入了旧数据或旧计划 |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |

## 用户回复

默认从 manifest 渲染：

```bash
python3 skills/analysis-run/scripts/render_user_reply.py --job-dir jobs/$SESSION_ID
```

只有在技术复核、排障或用户明确要求文件明细时，才加 `--technical` 输出内部相对路径。

---

## 内部脚本

主流程入口是 `init_or_resume_job.py`（创建/恢复 job）与 `render_user_reply.py`（从 manifest 渲染用户回复）。下列是配套内部工具，一般不单独调用：

| 脚本 | 角色 |
| --- | --- |
| `new_session_id.py` | 生成安全的 SESSION_ID / job id |
| `validate_analysis.py` | 校验 analysis.json 是否符合 `schemas/analysis.schema.json` |
| `cleanup_temp_csvs.py` | 清理 jobs/ 下临时 CSV（默认 dry-run，保留报告与计划） |
| `cleanup_job_csvs.py` | 清理指定 job CSV 产物的维护工具 |
