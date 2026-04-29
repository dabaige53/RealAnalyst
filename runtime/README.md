# Runtime

`runtime/` 是 RealAnalyst 的程序执行层。
它负责让分析流程稳定找到已注册数据源、字段、筛选器、source context 和本地 registry。

> 简单说：metadata 解释“指标是什么意思”，runtime 负责“怎么稳定取到数据”。

---

## Runtime 在整体架构中的位置

```mermaid
flowchart LR
    Meta[metadata context<br/>业务语义] --> Plan[analysis-plan]
    Plan --> Runtime[runtime<br/>source registry]
    Runtime --> T[data-export]
    Runtime --> D[data-export]
    T --> Job[jobs/{SESSION_ID}]
    D --> Job
```

---

## 子目录和文件

| 内容 | 作用 | 是否提交 |
| --- | --- | --- |
| `tableau/query_registry.py` | 查询已注册 Tableau source、字段、筛选器、source context | 提交 |
| `tableau/sqlite_store.py` | 读写本地 `registry.db` | 提交 |
| `tableau/source_context.py` | 组装 source 与指标/维度上下文 | 提交 |
| `duckdb/register_duckdb_sources.py` | 将 DuckDB catalog 注册成运行时 source | 提交 |
| `runtime.example.yaml` | 运行时配置示例 | 提交 |
| `tableau/registry.db` | 用户注册 source 后本地生成 | 不提交 |
| `runtime_config.db` | 本地迁移或运行时生成 | 不提交 |

---

## Metadata 与 Runtime 的区别

| 问题 | 去哪里找答案 |
| --- | --- |
| 指标怎么定义？ | `metadata/datasets/*.yaml` |
| 字段业务含义是什么？ | `metadata/datasets/*.yaml` |
| 这个 source 怎么取数？ | `runtime/` |
| 可用 filter / parameter 是什么？ | `runtime/tableau/query_registry.py` |
| DuckDB 表怎么注册？ | `runtime/duckdb/register_duckdb_sources.py` |
| 本轮分析用哪个 source？ | `analysis_plan.md` + runtime registry |

---

## 最小使用流程

```bash
# 查询 Tableau source
python3 runtime/tableau/query_registry.py --source <source_id>

# 查询筛选器
python3 runtime/tableau/query_registry.py --filter <source_id>

# 查询字段
python3 runtime/tableau/query_registry.py --fields <source_id>
```

DuckDB source 注册通常从 `metadata/sync/duckdb/catalog.example.json` 这类 catalog 快照开始，再进入 runtime 注册和 `data-export`。

---

## 常见卡点

| 卡点 | 说明 |
| --- | --- |
| registry.db 不在仓库里 | 正常，它是本地运行时生成文件 |
| runtime 中没有真实连接配置 | 正常，真实密钥放 `.env`，不提交 |
| metadata 和 runtime 信息不一致 | 以 metadata 解释业务口径，以 runtime 执行取数；不直接互相覆盖 |
| 取数失败 | 先查 runtime registry，再检查 skill 的导出参数 |
