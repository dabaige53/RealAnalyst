# DuckDB Runtime

这里保存 DuckDB 执行层代码。
它用于把 DuckDB catalog 注册成 RealAnalyst 可识别、可审计、可受控导出的 source。

---

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `register_duckdb_sources.py` | 读取 DuckDB catalog 快照，并注册成运行时 source |

---

## 推荐流程

```mermaid
flowchart TD
    A[metadata/sync/duckdb/catalog.json] --> B[register_duckdb_sources.py]
    B --> C[runtime registry]
    C --> D[data-export]
    D --> E[jobs/{SESSION_ID}/data/*.csv]
```

---

## DuckDB runtime 负责什么？

- 让 DuckDB table/view 变成已注册 source
- 保存 source 的 object、字段、粒度、时间字段等执行信息
- 支撑 `data-export` 做受控导出
- 避免 Agent 直接扫全库或自由 SQL 访问未知表

---

## 不负责什么？

| 不负责 | 应该放哪里 |
| --- | --- |
| 指标业务定义 | `metadata/datasets/*.yaml` |
| 真实数据库文件 | 本地私有路径，不上传 |
| 真实 catalog 快照 | `metadata/sync/duckdb/` 本地保存，不上传 |
| 跨表复杂 join 逻辑 | 需要单独设计，不默认在 runtime 中处理 |

---

## 常见卡点

| 卡点 | 解决办法 |
| --- | --- |
| DuckDB 表很多，不知道注册哪个 | 先在 metadata 中明确分析场景和粒度 |
| 字段名存在但无业务解释 | 回到 `metadata/datasets/` 补定义 |
| `data-export` 报字段不合法 | 确认字段已经进入 registry 白名单 |
