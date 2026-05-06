# Analysis Reference Skill

按需查询报告模板和分析框架配置，避免 Agent 读取大型配置文件。

---

## 什么时候用？

- 需要查报告模板（template）
- 需要查分析框架 logic_path / goal_template / dimension_type_hints

**不适用**：指标、字段、术语、数据集查询 → 使用 `RA:metadata-search`

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 关键词；查询类型：template / framework |
| 输出 | 机器可读 JSON 查询结果；framework 定义 |
| 下一步 | `RA:analysis-plan` |

---

## 快速示例

```bash
python3 skills/analysis-reference/scripts/query_config.py --template 月报
python3 skills/analysis-reference/scripts/query_config.py --framework mece
```

---

## 用户会得到什么？

- 按关键词匹配到的报告模板或框架配置。
- 机器可读 JSON，方便后续计划复用。
- 查询不到时的 available_frameworks 列表。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 要查指标/字段/术语 | 改用 `RA:metadata-search` |
| framework 返回 found=false | 查看 available_frameworks 选择最近似的框架 |
| 模板关键词匹配为空 | 换更宽泛的关键词，或直接读 `skills/report/references/template-system-v2.md` |
