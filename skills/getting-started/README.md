# Getting Started Skill

帮助新用户理解 RealAnalyst 的第一步：先准备 metadata，而不是直接写 SQL 或报告。

---

## 什么时候用？

- 刚安装 RealAnalyst
- 不知道要准备哪些数据源信息
- 想跑通 demo metadata
- 需要判断下一步该进入 metadata 还是 analysis-run

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 用户的初始化问题<br/>当前仓库是否已有 demo metadata<br/>是否已有 Tableau / DuckDB source 素材 |
| 输出 | 准备清单<br/>推荐路径<br/>可执行的 metadata 初始化命令 |
| 下一步 | `metadata` |

---

## 流程图

```mermaid
flowchart LR
    Start[用户第一次使用] --> Check[检查仓库和依赖] --> Prepare[准备数据集/字段/指标/证据] --> Metadata[进入 metadata skill] --> Analysis[进入 analysis-run]
```

---

## 快速示例

```bash
python3 skills/metadata/scripts/metadata.py init
python3 skills/metadata/scripts/metadata.py validate
```

---

## 用户会得到什么？

- 一份首次使用准备清单。
- 是否可以直接跑 demo 的判断。
- 下一步应该进入 `metadata` 还是 `analysis-run`。
- 初始化和校验 metadata 的可执行命令。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| 不知道是否该用这个 skill | 先看“什么时候用”；不确定时从 `analysis-run` 开始 |
| 找不到输入文件 | 回到上游 skill，确认是否已经生成正式产物 |
| 输出和预期不一致 | 先确认仓库是否已经初始化 demo metadata |
| 涉及 `needs_review` | 报告里必须标注为待确认或推断口径 |
| 涉及新增数据源 | 先让用户确认，再执行 |
