# Metadata Skill

统一处理数据集注册、字段/指标/术语维护、校验、索引、搜索和 context pack 生成。

---

## 什么时候用？

- 注册新数据集
- 维护字段或指标定义
- 分析前查询口径
- Tableau / DuckDB onboarding 后整理语义层
- 生成 analysis-plan 的 context

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | metadata/datasets/*.yaml<br/>metadata/sync/ 中的同步素材<br/>source id<br/>指标/字段/术语关键词 |
| 输出 | validate 结果<br/>metadata/index/*.jsonl<br/>search 结果<br/>context pack<br/>可选 OSI export |
| 下一步 | `analysis-plan` |

---

## 流程图

```mermaid
flowchart LR
    Sync[connector 素材] --> YAML[dataset YAML] --> Validate[validate] --> Index[index] --> Search[search] --> Context[context pack] --> Plan[analysis-plan]
```

---

## 快速示例

```bash
python3 skills/metadata/scripts/metadata.py validate
python3 skills/metadata/scripts/metadata.py index
python3 skills/metadata/scripts/metadata.py search --type all --query revenue
python3 skills/metadata/scripts/metadata.py context --dataset-id demo.retail.orders --metric total_revenue
```

---

## 用户会得到什么？

- 可校验的 dataset YAML。
- 字段、指标、术语和 open questions 的维护结果。
- 可搜索的 metadata index。
- 本轮分析需要的 context pack。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 检查 YAML 中的 source id、metric id 和 review 状态 |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
