# 日志与输出规范

> RealAnalyst 当前没有统一 Python logging framework。脚本主要通过 JSON stdout、简短状态行、append-only JSONL 审计文件和 Markdown report 与 agent/用户沟通。

---

## 输出模型

按受众选择输出通道：

| 通道 | 受众 | 真实示例 |
| --- | --- | --- |
| JSON stdout | agent / 脚本调用方 | `metadata.py list-commands`、`sync_registry.py`、`skills/data-profile/scripts/run.py`、`skills/metadata-search/scripts/search.py` |
| 简短状态行 | 人类操作者 | `scripts/install_codex_plugin.py`、`skills/metadata-report/scripts/generate_report.py` |
| 追加式 JSONL audit | job lineage / metadata 维护追踪 | `scripts/log_acquisition.py`、`metadata/audit/metadata_changes.jsonl`、`metadata/audit/metadata_relations.jsonl` |
| Markdown report | 用户复核 | `metadata/audit/metadata_change_report.md`、`metadata/sync/*/reports/*.md` |

不要向 stdout 被 JSON parser 消费的脚本加入 debug 行。

---

## 结构化 stdout（JSON）

当命令会被另一个 skill 或测试调用时，stdout 在成功时应是合法 JSON，在预期失败时也应是结构化 JSON。

示例：

- `skills/metadata/scripts/sync_registry.py` 输出 `success`、`dry_run`、`registry_db` 和 per-dataset `results`。
- `skills/metadata-search/scripts/search.py` 输出 `success`、`query`、`type`、`backend` 和 `matches`。
- `skills/data-profile/scripts/run.py` 输出 profile result 或结构化 error object。

如果底层函数会打印诊断信息，先捕获，再输出最终 JSON。`skills/data-profile/scripts/run.py` 用 `redirect_stdout(log_buffer)` 包住 `profile_data()`，确保 wrapper 的 stdout 干净。

---

## 人类状态行

只有不会被机器解析 stdout 的命令才输出简短状态行。

当前模式：

- `skills/metadata-report/scripts/generate_report.py` 输出 `[OK] report -> <path>`。
- 没有匹配目标时输出 `[WARN] No DuckDB entries matched`。
- metadata 校验失败时输出 `[Error] metadata validate failed:`。
- `scripts/install_codex_plugin.py` 输出 `$ copytree <source> -> <target>` 和最终安装摘要。

状态行要具体、路径导向，不要从 library function 打进度 banner。

---

## 审计日志

事件 lineage 使用 append-only JSONL：

- `scripts/log_acquisition.py` 追加 acquisition events 到 `.meta/acquisition_log.jsonl`。
- `skills/metadata/scripts/metadata.py record-change` 委托 `metadata_audit.py`，更新 `metadata/audit/metadata_changes.jsonl`。
- `metadata.py record-relation` 把 `business_definition.ref` 关系写入 `metadata/audit/metadata_relations.jsonl`。

审计记录应包含足够上下文：

- source backend 或 dataset id。
- output path 或 changed metadata path。
- timestamp。
- reason / summary。
- relevant confirmation flags。

正常操作中不要重写历史审计记录。

---

## 应输出什么

应该输出或记录：

- 生成 artifact、report、summary 的路径。
- dataset id / source id / connector scope。
- 带准确 metadata key path 的 validation errors / warnings。
- Registry sync 状态：`preview`、`synced`、`invalid`。
- Export lineage：source id、selected fields、filters、date ranges、row count、summary file。
- 输出来源：来自 `export_summary`、`duckdb_export_summary` 还是显式用户输入。
- 缺依赖信息和安装命令。

---

## 禁止输出什么

不要输出：

- credentials、tokens、Tableau passwords、API keys、cookies、`.env` values。
- 完整敏感 source files 或原始业务数据集。
- 用户机密文档，除非它们被有意归档为 `metadata/sources/` evidence。
- 正常日志中的整行 CSV 数据。
- 编造的占位行或泛化提醒。

Sample values 只可用于识别值域或格式，不是完整枚举，也不是业务定义。

---

## 状态词汇

当前没有 `logging` module level policy。打印状态行时使用这些词：

- `[OK]` 表示输出完成，并附路径。
- `[WARN]` 表示非致命的 no-target / no-sample / no-match。
- `[Error]` 表示 validation 或 CLI mode failure，命令停止。

不要引入第二套状态词，除非整个项目统一迁到标准 `logging` module。

---

## 脚本 stdout 契约

每个脚本只能选择一种 stdout contract：

1. JSON-only stdout。
2. Human status stdout。
3. Generated file path / status stdout。

不要把 JSON payload 和人类进度行混在同一个命令中，除非现有脚本已经是这种 contract 且没有调用方解析 stdout。

当 wrapper 调用 noisy function 时，redirect 或 suppress 内部 stdout，再输出一个最终 JSON payload。这样比让调用方从混合输出中解析更稳。

---

## 常见错误

- JSON 前打印 debug 行，导致 `json.loads(proc.stdout)` 测试失败。
- 每个字段/指标都打日志；多数场景只需要 summary count 和 report path。
- 在 metadata report 中重复 generic usage note，而不是报告具体 gap。
- 把 sample 当成完整 enum 输出。
- 把生成路径藏在 prose 里，而不是放进 JSON 或清晰的 `[OK] report ->` 状态行。
