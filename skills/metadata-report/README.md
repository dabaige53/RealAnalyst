# RA:metadata-report

把 RealAnalyst 的数据集元数据、运行注册状态和待维护项写成可复核的 Markdown 报告。报告面向准备使用数据做分析的人，只展示已经维护在 metadata / runtime registry / metadata search-read-status 体系里的事实。

---

## 什么时候用？

- 需要生成、补齐或解释元数据 Markdown 报告。
- 需要说明某个 dataset 已维护了哪些字段、指标、筛选值、映射和注册状态。
- 需要做元数据清单、注册结果说明、字段口径补齐清单或待补齐项报告。

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
| connector discovery/sync 素材 | Tableau / DuckDB 字段、筛选器、参数或 catalog 发现结果 |
| `metadata/audit/*` | 只作为审计和维护追溯层，不作为业务定义真源 |

## 主要输出

| 输出 | 说明 |
| --- | --- |
| Dataset-first 元数据报告 | `metadata/reports/<dataset_id>_metadata_report.md` |

---

## 快速开始

```bash
# 单个数据集元数据报告
python3 skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id>

# 全部数据集元数据报告
python3 skills/metadata-report/scripts/generate_report.py --all

# 指定输出目录
python3 skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id> --output-dir metadata/reports
```

旧的 `--connector tableau|duckdb` 入口仅作为 connector 同步报告兼容路径保留；新文档和日常使用优先 dataset-first。

---

## 常见卡点

| 卡点 | 处理 |
| --- | --- |
| registry 不存在或未注册 | 报告继续生成，运行与注册状态显示“未注册” |
| 字段定义、指标定义或取值范围缺失 | 单元格显示“未维护”，并进入“未维护项” |
| 不知道用哪个脚本入口 | 统一用 `skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id>` |
| 想写分析结论 | 不要用本 skill；分析结论报告使用 `RA:report` |
| 需要 agent 读取结构化元数据 | 使用 `python3 skills/metadata/scripts/metadata.py read --dataset-id <dataset_id>`，不要从 Markdown 反解析 |

---

## 与其他 skill 的关系

- **RA:metadata** → 负责维护 YAML、注册数据集、生成索引和上下文。metadata-report 只负责把元数据写成报告。
- **RA:report** → 负责写分析结论报告。metadata-report 不输出业务经营结论。
- **RA:getting-started** → 初次使用时可能需要先跑 getting-started，再用 metadata-report 检视注册结果。

---

## 内部脚本

`generate_report.py` 是统一入口；下列是它背后的内部模块，一般不单独调用：

| 脚本 | 角色 |
| --- | --- |
| `_bootstrap.py` | 定位 workspace 根目录的内部 helper |
| `report_context.py` | 构建报告上下文与 Markdown 渲染（被各 renderer 共用） |
| `dataset_report.py` | dataset-first 元数据报告渲染 |
| `duckdb_report.py` | DuckDB connector 同步报告渲染（兼容入口） |
| `tableau_report.py` | Tableau 元数据报告渲染（兼容入口） |
