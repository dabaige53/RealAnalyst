# RealAnalyst validation report

本报告记录本次合并与静态/冒烟验证结果。

## 已完成修复

1. 将原 `tableau-export` 与 `duckdb-export` 合并为 `skills/data-export`。
   - Tableau 脚本保留在 `skills/data-export/scripts/tableau/`。
   - DuckDB 脚本保留在 `skills/data-export/scripts/duckdb/`。
   - 原参考文档分别保留在 `references/tableau/` 与 `references/duckdb/`。
2. 修复 wrapper 内部路径：
   - `tableau_export_with_meta.py` 指向 `skills/data-export/scripts/tableau/export_source.py`。
   - `duckdb_export_with_meta.py` 指向 `skills/data-export/scripts/duckdb/export_duckdb_source.py`。
   - `profiling_with_meta.py` 指向 `skills/data-profile/scripts/run.py`。
3. 补齐共享日志模块 `lib/log_utils.py`，避免 `data-profile` 与 `report-verify` 导入失败。
4. 修复 `skills/data-profile/scripts/profile.py` 中 `yaml` / `YAML_AVAILABLE` 未定义的问题。
5. 将 `duckdb` 加入 `requirements.txt` 与 `scripts/setup_venv.sh` 检查项。
6. 新增可公开提交的 demo 数据：
   - `examples/data/retail_orders.csv`
   - `examples/data/retail_forecast.csv`
   - `examples/build_demo_duckdb.py`
7. 更新 DuckDB 示例 catalog、runtime 注册脚本和 demo metadata，使 demo registry 能发现两个 DuckDB source。
8. 更新 `.codex-plugin/plugin.json`、根 README、skills README、runtime 文档和 sync 文档，统一使用 `data-export`。

## 已执行验证

| 验证项 | 结果 |
| --- | --- |
| 全项目 Python 语法编译 | 通过 |
| `.codex-plugin/plugin.json` JSON 校验 | 通过 |
| `metadata/sync/duckdb/catalog.example.json` JSON 校验 | 通过 |
| 所有 `skills/*/SKILL.md` frontmatter 快速校验 | 通过 |
| `skills/metadata/scripts/metadata.py validate` | 通过 |
| `skills/metadata/scripts/metadata.py index` | 通过 |
| `skills/metadata/scripts/metadata.py context --source-id demo.retail.orders --metric total_revenue` | 通过 |
| `skills/data-profile/scripts/profiling_with_meta.py` 使用 demo CSV 冒烟运行 | 通过 |
| `data-export` Tableau / DuckDB CLI `--help` | 通过 |
| `report-verify` CLI `--help` | 通过 |
| DuckDB registry `--dry-run` | 通过 |
| DuckDB registry register + `query_registry.py --search forecast` | 通过 |

## 沙箱限制下未做的验证

1. 未连接真实 Tableau Server，因此 Tableau 只验证了 CLI、路径解析、registry 对接入口；真实导出需要用户提供 Tableau 环境变量和已注册 source。
2. 当前沙箱没有预装 `duckdb` 包；已将其加入依赖，并让 DuckDB CLI 的帮助命令在未安装依赖时也能正常显示。完整 DuckDB 导出请在安装依赖后运行：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 examples/build_demo_duckdb.py
./scripts/py runtime/duckdb/register_duckdb_sources.py
./scripts/py skills/data-export/scripts/duckdb/run_tests.py
```

## 架构判断

当前架构整体合理：metadata 作为事实源，runtime registry 作为可执行 source 索引，`data-export` 负责受控取数，`data-profile` 负责数据画像，`analysis-run` / `report` / `report-verify` 负责分析和报告闭环。合并后入口更清晰，Codex 不再需要在两个导出 skill 间选择。

仍建议后续补充：

- 一个端到端 CI workflow，至少运行 JSON 校验、skill 校验、metadata validate/index/context、profile smoke test。
- 一个真实但脱敏的 Tableau registry 示例，覆盖 `vf` / `vp` / domain view 三类导出。
- 一个包含异常数据的 demo CSV，用于验证 `report-verify` 和 profile 信号。
