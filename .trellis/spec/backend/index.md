# 后端开发规范

> RealAnalyst 的“后端”不是 Web API，而是一组 Codex skill、Python CLI、metadata 分层文件、runtime registry 和分析作业脚本。后续 coding agent 必须按这些真实约定开发。

---

## 适用范围

本目录记录 RealAnalyst 的真实工程约定，供 `trellis-implement` 和 `trellis-check` 在写代码、审查代码时加载。这里写“当前仓库实际怎么做”，不写抽象理想模板。

文档语言要求：

- 规则、解释、表格说明使用简体中文。
- 文件路径、命令、函数名、类名、配置键和 skill 名保留原文。
- 业务口径可以使用中文，例如“业务定义待确认”“元数据待修复报告”。

---

## 规范索引

| 规范 | 内容 | 状态 |
| --- | --- | --- |
| [目录结构](./directory-structure.md) | skill、metadata、runtime、jobs、脚本入口的职责边界 | 已填充 |
| [数据库与取数](./database-guidelines.md) | SQLite runtime registry、FTS5 index、DuckDB export 的使用边界 | 已填充 |
| [错误处理](./error-handling.md) | CLI、JSON 输出、metadata validation、export/report 错误处理 | 已填充 |
| [日志与输出](./logging-guidelines.md) | JSON stdout、人类状态行、审计 JSONL、Markdown report 的输出契约 | 已填充 |
| [质量规范](./quality-guidelines.md) | 测试、校验、禁止模式、review checklist | 已填充 |

---

## 使用方式

开发前先读与改动相关的规范文件。尤其注意：

- metadata YAML、mapping、dictionary、runtime registry、search index、sync report 和 analysis report 不得互相替代。
- 修改 metadata 行为时，优先跑 `metadata validate`、`metadata index`，需要 export-ready 时再跑 `metadata sync-registry` / `metadata status`。
- 修改 skill、installer、metadata-report、runtime registry 时，必须同时检查 README、skill contract、script、tests 是否需要同步。
- 代码示例必须来自真实文件路径，不使用占位内容。
