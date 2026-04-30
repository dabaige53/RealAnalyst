# RA:metadata-report

把 RealAnalyst 的元数据、connector 同步结果、数据源注册信息和待 review 问题写成可复核的 Markdown 报告。

---

## 什么时候用？

- 需要生成、补齐或解释 metadata Markdown 报告。
- 需要说明 Tableau / DuckDB sync report 中同步了什么、哪些字段进入 metadata、哪些仍待确认。
- 需要做 metadata inventory、注册结果说明、字段口径审阅清单或 review gap 报告。

**不要用于**：

- 维护 YAML、注册数据集、生成 index/context → 使用 `RA:metadata`。
- 导出真实数据 → 使用 `RA:data-export`。
- 写分析结论报告 → 使用 `RA:report`。
- 验证分析报告质量 → 使用 `RA:report-verify`。

---

## 主要输入

| 输入 | 来源 |
| --- | --- |
| `metadata/datasets/*.yaml` | 数据集说明、字段、指标、时间字段、粒度、适用边界 |
| `metadata/mappings/*.yaml` | 源字段到标准语义的映射 |
| `metadata/dictionaries/*.yaml` | 公共指标、维度、术语定义 |
| `metadata/sources/` | 原始证据、用户文档、connector discovery 归档 |
| connector sync 脚本输出 | Tableau / DuckDB 同步明细 |

## 主要输出

| 输出 | 说明 |
| --- | --- |
| Tableau 元数据报告 | `metadata/sync/tableau/reports/*.md` |
| DuckDB 元数据报告 | `metadata/sync/duckdb/reports/*.md` |

---

## 快速开始

```bash
# Tableau 数据源元数据报告
python3 skills/metadata/adapters/tableau/scripts/generate_sync_report.py --key <source_key>

# DuckDB 单数据集注册报告（基于 YAML）
python3 skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --dataset-id <dataset_id>

# DuckDB 全部数据集注册报告（基于 YAML）
python3 skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --all-yaml
```

---

## 常见卡点

| 卡点 | 处理 |
| --- | --- |
| validate 失败 | 报告降级为"元数据待修复报告"，失败项进入待确认问题 |
| 不知道用哪个脚本入口 | 优先用 `--dataset-id`（基于 YAML）；只有需要运行时取数状态时才用 `--key`（基于 registry） |
| 想写分析结论 | 不要用本 skill；分析结论报告使用 `RA:report` |
| 字段名看不懂 | 回到 `metadata/dictionaries/` 和 `metadata/mappings/` 找证据；找不到就标记待确认 |

---

## 与其他 skill 的关系

- **RA:metadata** → 负责维护 YAML、注册数据集、生成 index/context。metadata-report 只负责把元数据写成报告。
- **RA:report** → 负责写分析结论报告。metadata-report 不输出业务经营结论。
- **RA:getting-started** → 初次使用时可能需要先跑 getting-started，再用 metadata-report 检视注册结果。
