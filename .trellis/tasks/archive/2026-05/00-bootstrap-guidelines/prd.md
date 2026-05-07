# 规范初始化任务：填充项目开发规范

**运行对象：AI agent。开发者通常不会直接阅读本文件。**

开发者刚在本项目运行了 `trellis init`。仓库现在有 `.trellis/` 规范骨架，本任务位于 `.trellis/tasks/00-bootstrap-guidelines/`。

你的职责是把 `.trellis/spec/` 填成团队真实开发规范。未来本项目的 `trellis-implement` 和 `trellis-check` 子代理会通过每个任务的 `implement.jsonl` / `check.jsonl` 自动加载这些规范。空 spec 会让子代理写泛化代码；真实 spec 会让子代理匹配 RealAnalyst 的实际模式。

---

## 状态

- [x] 填充 backend guidelines
- [x] 加入真实代码/路径示例
- [x] backend spec 正文使用简体中文

---

## 需要填充的 spec 文件

### 后端规范

| 文件 | 需要记录的内容 |
| --- | --- |
| `.trellis/spec/backend/directory-structure.md` | skill、metadata、runtime、jobs、脚本入口的职责边界 |
| `.trellis/spec/backend/database-guidelines.md` | SQLite runtime registry、FTS5 index、DuckDB export 的使用边界 |
| `.trellis/spec/backend/error-handling.md` | CLI、JSON 输出、metadata validation、export/report 错误处理 |
| `.trellis/spec/backend/logging-guidelines.md` | JSON stdout、人类状态行、审计 JSONL、Markdown report 的输出契约 |
| `.trellis/spec/backend/quality-guidelines.md` | 测试、校验、禁止模式、review checklist |

### 思考指南

`.trellis/spec/guides/` 已包含通用 thinking guides。只有当它明显不适合 RealAnalyst 时才调整。

---

## 填充方式

### 1. 优先从现有约定文件导入

先读取仓库已有约定，再把相关规则放入对应 `.trellis/spec/` 文件。

| 文件 / 目录 | 来源 |
| --- | --- |
| `AGENTS.md` | Codex / Claude Code / agent-compatible tools |
| `CLAUDE.md` / `CLAUDE.local.md` | Claude Code / GitNexus 生成说明 |
| `README.md` | 产品流程和安装入口 |
| `skills/README.md` | skill 总览和执行链路 |
| `metadata/README.md` | metadata 分层说明 |
| `docs/metadata-lookup-workflow.md` | metadata lookup workflow |
| `.github/workflows/ci.yml` | CI 验证入口 |
| `tests/test_metadata_product_fixes.py` | 当前主要回归测试 |

### 2. 从真实代码补足约定

每个 spec 文件至少引用 2-3 个真实路径或真实代码模式。不要写假想架构，也不要使用占位内容。

重点观察：

- `skills/metadata/scripts/metadata.py`
- `skills/metadata/scripts/validate_metadata.py`
- `skills/metadata/scripts/sync_registry.py`
- `runtime/tableau/sqlite_store.py`
- `skills/data-export/scripts/duckdb/export_duckdb_source.py`
- `skills/data-profile/scripts/run.py`
- `skills/metadata-report/scripts/generate_report.py`
- `scripts/install_codex_plugin.py`
- `scripts/log_acquisition.py`
- `scripts/update_artifact_index.py`

### 3. 记录现实，不写理想模板

spec 必须写“当前代码实际怎么做”。不要写抽象最佳实践，也不要把未来想重构的目标当成现状。

如果存在技术债，记录当前状态即可；改进是后续任务，不属于 bootstrap。

### 4. 文档语言

开发者明确要求 backend spec 正文使用简体中文。

- 规则、解释、表格说明使用简体中文。
- 文件路径、命令、函数名、类名、配置键、skill 名保留原文，便于检索。
- 业务口径可以使用中文，例如“业务定义待确认”“元数据待修复报告”。

---

## 完成标准

- `.trellis/spec/backend/*.md` 均已填充真实内容。
- 没有 Trellis 初始占位文本、英文模板说明或“必须英文”的残留。
- `index.md` 已把所有 backend 规范标为已填充。
- 每个规范都有真实路径、命令或代码模式示例。
- 内容遵守 RealAnalyst 的职责独立和 metadata 分层边界。

---

## 验证建议

```bash
rg -n "占位|模板|必须英文" .trellis/spec/backend
find .trellis/spec/backend -maxdepth 1 -type f -name '*.md' -exec wc -l {} +
python3 skills/metadata/scripts/metadata.py validate
```

若开发者确认完成，可继续运行：

```bash
python3 ./.trellis/scripts/task.py finish
python3 ./.trellis/scripts/task.py archive 00-bootstrap-guidelines
```
