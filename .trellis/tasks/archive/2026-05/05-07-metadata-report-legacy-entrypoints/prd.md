# 修复 metadata adapter 旧报告入口

## 背景

当前未提交变更新增了两个 adapter 级 `generate_sync_report.py`：

- `skills/metadata/adapters/duckdb/scripts/generate_sync_report.py`
- `skills/metadata/adapters/tableau/scripts/generate_sync_report.py`

它们重新暴露旧的 standalone report renderer，绕过 `RA:metadata-report` 的统一入口和本次元数据/审计层隔离调整。

## 目标

- 保留旧路径兼容性，但旧路径只能转发到 `skills/metadata-report/scripts/generate_report.py`。
- 旧路径不得再直接拼 Markdown、不得再生成旧 `*_sync_report.md` 结构。
- DuckDB legacy wrapper 使用 `--connector duckdb`。
- Tableau legacy wrapper 使用 `--connector tableau`。
- 继续支持原 legacy 参数中的 `--key`、`--all`、`--report-dir`、step status、`--with-samples`、`--export-summary`、`--manifest` 等可安全映射的参数。

## 非目标

- 不改统一 metadata-report renderer。
- 不新增业务报告字段。
- 不恢复旧 sync report 格式。

## 验收

- 两个 legacy 脚本不包含 `render_sync_report` 或手写 Markdown 章节。
- 运行 legacy 脚本时实际调用统一 `generate_report.py`。
- 测试覆盖旧路径不再包含旧报告渲染内容。
