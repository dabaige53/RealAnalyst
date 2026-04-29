# Reference Lookup Skill

按需查询 runtime 中的指标、维度、术语、模板和分析框架，避免 Agent 读取大型配置文件。

---

## 什么时候用？

- 需要查某个指标定义
- 需要查报告模板
- 需要查分析框架 logic_path
- 需要查维度或术语

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 关键词<br/>查询类型：template / glossary / metric / framework / dimension |
| 输出 | 机器可读 JSON 查询结果<br/>matches<br/>framework 定义 |
| 下一步 | `RA:analysis-plan / RA:report` |

---

## 流程图

```mermaid
flowchart LR
    Query[关键词] --> Config[runtime 配置] --> Result[JSON 查询结果] --> Plan[analysis-plan / report]
```

---

## 快速示例

```bash
python3 skills/reference-lookup/scripts/query_config.py --metric 收入
python3 skills/reference-lookup/scripts/query_config.py --framework mece
```

---

## 用户会得到什么？

- 按关键词匹配到的指标、术语、模板或框架。
- 机器可读 JSON，方便后续计划和报告复用。
- 查询不到时的下一步维护建议。
- 避免一次性读取大配置文件的轻量查询路径。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `RA:analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 换更具体的关键词，或回到 metadata 补定义 |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
