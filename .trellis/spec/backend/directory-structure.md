# 目录结构

> RealAnalyst 是平台无关的 metadata-first 分析执行系统，当前第一套 adapter 是本地 Python CLI + Codex skill 工作台；没有 route/service/controller 这种 Web API 分层。目录结构的核心是职责独立：每个 skill、脚本、metadata 层、runtime 文件和 job artifact 只承担自己的职责。

---

## 系统形态

RealAnalyst 围绕三核和 adapter entrypoints 组织。核心边界是：Metadata 管“含义”，Runtime Registry 管“能不能取”，Job 管“这次实际用了什么”。Codex skills 是当前用户入口，不是产品边界。

- `skills/<skill-name>/SKILL.md` 是 agent 执行契约。
- `skills/<skill-name>/README.md` 是用户和维护者文档。
- `skills/<skill-name>/scripts/` 放可执行 Python CLI 入口。
- `skills/<skill-name>/references/` 放 skill 需要加载的细分契约。
- `skills/<skill-name>/agents/` 放可选子代理配置。
- `runtime/` 放运行态支持和 SQLite registry，承接 source、field、filter、parameter 和 source group 等可执行能力。
- `metadata/` 放语义元数据真源、证据层和生成层，承接字段、指标、术语、定义状态和 evidence relation。
- `schemas/` 放结构化 artifact 的 JSON Schema。
- `jobs/{SESSION_ID}/` 是单次分析作业目录，保存本次 plan、export、profile、analysis、report、verification、feedback 和 artifact index；不承担长期任务管理。

根 [README.md](/Users/w/Documents/GitHub/RealAnalyst/README.md) 把产品流程定义为：先注册/维护元数据，再做分析规划、取数、画像、报告和验证。代码结构也按这条链路组织，不按传统后端服务分层组织。

---

## 职责边界（skill）

每个 skill 只拥有一个主职责。一个 skill 的脚本不要顺手完成另一个 skill 的主职责；需要交接时，输出下游 owner 需要的 artifact、命令或报告路径。

用户入口必须保持分层：

- 普通用户主入口只放 `RA:getting-started`、`RA:metadata`、`RA:analysis-run`。
- 常见补充入口是 `RA:metadata-report`、`RA:metadata-refine`、`RA:report-verify`。
- `RA:analysis-plan`、`RA:data-export`、`RA:data-profile`、`RA:report` 是流程内工具，通常由 `RA:analysis-run` 编排。
- `RA:metadata-search`、`RA:artifact-fusion`、`RA:analysis-reference` 是辅助/高级工具；`RA:reference-lookup` 是 legacy compatibility entrypoint。
- `RA:getting-started` 是 lightweight guide + skill router + minimal status check，不创建正式 job、不取数、不写报告、不自动注册 metadata。
- 每个 `skills/*/SKILL.md` 只能有一个 `## Completion Summary`，并按“完成情况 / 下一步建议 / 边界提醒”给出短小、可执行的交接提示。

| 区域 | Owner | 真实示例 |
| --- | --- | --- |
| metadata YAML、index、context、registry sync | `RA:metadata` | `skills/metadata/scripts/metadata.py`、`skills/metadata/scripts/validate_metadata.py`、`skills/metadata/scripts/sync_registry.py` |
| 元数据 Markdown 报告 | `RA:metadata-report` | `skills/metadata-report/scripts/generate_report.py`、`skills/metadata-report/scripts/duckdb_report.py`、`skills/metadata-report/scripts/tableau_report.py` |
| 受控取数 | `RA:data-export` | `skills/data-export/scripts/duckdb/export_duckdb_source.py`、`skills/data-export/scripts/tableau/tableau_export_with_meta.py` |
| 数据画像 | `RA:data-profile` | `skills/data-profile/scripts/run.py`、`skills/data-profile/scripts/profile.py` |
| 分析作业编排 | `RA:analysis-run` | `skills/analysis-run/scripts/init_or_resume_job.py`、`skills/analysis-run/scripts/validate_analysis.py` |
| 报告验证 | `RA:report-verify` | `skills/report-verify/scripts/verify.py` |
| 多源 artifact 融合 | `RA:artifact-fusion` | `skills/artifact-fusion/scripts/fusion.py` |

例如 Tableau/DuckDB connector adapter 可以生成初始化材料和同步状态提示，但不能变成业务定义真源，也不能接管 Markdown metadata report。历史兼容的 adapter `generate_sync_report.py` 路径只能转发到 `RA:metadata-report` 的统一入口，不得保留 standalone renderer。`skills/metadata/references/connector-adapters.md` 已把报告生成交给 `RA:metadata-report`。

---

## 元数据分层（metadata）

`metadata/` 是分层语义系统，不是一个大 YAML 仓库：

```text
metadata/
├── sources/        # 原始证据、用户文档、connector discovery 归档
├── dictionaries/   # 稳定指标、维度、术语定义
├── mappings/       # source field -> 标准语义映射
├── datasets/       # 一个真实可分析数据集对应一个 YAML
├── audit/          # 维护日志、relation records、review trails
├── models/         # semantic model grouping
├── sync/           # connector sync snapshots 和生成的 sync reports
├── index/          # 生成的 JSONL + FTS5 search.db 检索层
└── osi/            # 生成的语义交换输出
```

必须遵守：

- `metadata/datasets/*.yaml` 保持轻量，只放语义身份、字段、指标、业务边界和引用关系。
- 不把 `sample_profile`、`sample_values`、`top_values`、`enum_values`、`source_mapping`、`duckdb_type`、`nullable`、registry snapshot 或 report 内容塞进 dataset YAML。
- `metadata/index/` 和 `metadata/osi/` 是生成层，禁止人工编辑。
- `metadata/sync/reports/` 是同步审计输出，不是业务定义真源。
- 字段或指标使用 `business_definition.ref` 时，关联关系写入 `metadata/audit/metadata_relations.jsonl`，不要把证据展开复制回 dataset YAML。

真实文件示例：

- `metadata/datasets/demo.retail.orders.yaml`
- `metadata/mappings/demo.retail.orders.mapping.yaml`
- `metadata/dictionaries/demo.retail.dictionary.yaml`
- `metadata/sync/duckdb/catalog.example.json`
- `metadata/index/fields.jsonl`

---

## 运行态布局（runtime）

`runtime/` 是运行态层：

```text
runtime/
├── registry.db
├── paths.py
├── runtime_config_store.py
├── tableau/
└── duckdb/
```

`runtime/paths.py` 是 runtime DB 路径的单一来源：

```python
RUNTIME_DIR = WORKSPACE_DIR / "runtime"
RUNTIME_DB_PATH = RUNTIME_DIR / "registry.db"
```

`runtime/tableau/sqlite_store.py` 是 SQLite store，负责 entries、specs、enums、source groups 和兼容 registry document loading。新增 registry 读写时，优先加窄 helper，不要在其它脚本里随手写 JSON/YAML 副本。

---

## 命令行入口模式（CLI）

多数脚本是直接 Python CLI，使用 `argparse`、`pathlib.Path` 和 JSON 输出。聚合入口的真实模式是 `skills/metadata/scripts/metadata.py`：

```python
COMMANDS = (
    "init",
    "validate",
    "index",
    "search",
    "context",
    "sync-registry",
    "status",
)

def run_python_script(workspace: Path, script: Path, args: list[str]) -> int:
    completed = subprocess.run([sys.executable, str(script), *args], cwd=workspace, check=False)
    return completed.returncode
```

新增 metadata 命令时：

- 在 `metadata.py` 增加 subcommand。
- 透传 `--workspace`。
- 实现放在 `skills/metadata/scripts/` 下的独立脚本。
- 不要把多个 skill 的职责塞进一个聚合脚本。

---

## 工作区发现（workspace）

脚本必须同时适配源码仓和 project-local 安装后的 `.agents/skills` 布局。

遵循现有 bootstrap 模式：

- `skills/metadata/scripts/_bootstrap.py` 通过 `ANALYST_WORKSPACE_DIR`、`skills/ + metadata/`、`.agents/skills/` 寻找 workspace。
- 安装副本兼容脚本在需要时把 `.agents` 加入 `sys.path`。例如 `skills/metadata-report/scripts/duckdb_report.py` 使用 `AGENTS_DIR = WORKSPACE_DIR / ".agents"` 再导入 `runtime` 或 `skills`。
- 作业脚本可以通过 `runtime/` 加 `.agents/skills/` 或 `skills/` 判断 workspace，参考 `skills/data-profile/scripts/run.py`。

不要在可复用 skill 脚本里硬编码这个仓库根路径。

---

## 作业与产物（jobs/artifacts）

分析 artifact 放在 `jobs/{SESSION_ID}/`：

```text
jobs/{SESSION_ID}/
├── data/
├── profile/
├── .meta/
├── analysis.json
├── export_summary.json
├── duckdb_export_summary.json
└── 报告_{topic}_{time}.md
```

遵循现有 artifact contract：

- `skills/data-export/scripts/duckdb/export_duckdb_source.py` 写 `jobs/{session_id}/data/<output-name>` 和 `duckdb_export_summary.json`。
- `skills/data-profile/scripts/run.py` 按顺序从 `export_summary.json`、`duckdb_export_summary.json`、显式 `--data-csv` 解析正式 CSV。
- `scripts/update_artifact_index.py` 更新 `.meta/artifact_index.json`。
- `scripts/log_acquisition.py` 追加 `.meta/acquisition_log.jsonl`。

不要猜测生成路径。读取 `export_summary.json`、`duckdb_export_summary.json` 或 `artifact_index.json`。

---

## 命名约定

- Skill 目录用 kebab-case：`analysis-run`、`metadata-report`、`artifact-fusion`。
- Python 脚本用 snake_case：`sync_registry.py`、`build_context.py`、`export_duckdb_source.py`。
- Dataset YAML 文件名使用 dataset id：`metadata/datasets/demo.retail.orders.yaml`。
- Mapping 文件追加 `.mapping.yaml`：`metadata/mappings/demo.retail.orders.mapping.yaml`。
- Runtime source id 和 dataset id 使用 dotted string：`demo.retail.orders`。
- 生成报告文件名包含时间戳和 source id，例如 `metadata/sync/duckdb/reports/20260506_162846_demo.retail.orders_metadata_report.md`。

---

## 禁止的结构改动

- 安装或文档任务中不要新建业务工作区顶层目录；`metadata/`、`runtime/`、`jobs/`、`logs/` 只由对应 runtime flow 创建。
- 不要把 runtime YAML/config 复制进 `skills/`。
- 不要把 profile、enum、mapping、registry、report、analysis result 内容放进 `metadata/datasets/*.yaml`。
- 不要手工编辑 `metadata/index/` 或 `metadata/osi/`。
- 新增用户可见 skill 时，同步更新 `skills/README.md` 和根 README 的 skill 列表。
