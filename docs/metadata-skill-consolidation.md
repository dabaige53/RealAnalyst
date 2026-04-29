# Metadata Skill 收敛说明

## 统一入口：metadata

RealAnalyst 的元数据维护入口收敛为 `RA:metadata`。用户需要注册数据集、初始化字段、维护指标、搜索术语、构造分析上下文时，都先进入 `RA:metadata`。

## 分层架构

| 层级 | 职责 |
| --- | --- |
| metadata skill | 用户可见主入口 |
| Tableau/DuckDB connector adapter | 发现外部系统元数据，提供初始化素材 |
| sources | 原始材料和审计证据 |
| dictionaries | 公共指标、维度、术语 |
| mappings | source 字段到标准语义的映射 |
| datasets | 真实可分析数据源 metadata |
| index | 低 token 检索层 |
| context pack | 分析对话层 |
| registry.db | 运行层 |
| OSI | 交换层 |

Tableau/DuckDB 是 connector adapter，不再作为用户优先选择的同步 skill。

YAML 是 LLM 维护真源，但要分层维护：公共语义进 dictionaries，字段映射进 mappings，真实数据源进 datasets，原始材料先归档到 sources。

registry.db 是运行层，服务数据导出与执行稳定性；当前阶段不从 YAML 反写 registry.db。

OSI 是交换层，不进入本地分析主路径。

## 日常流程

```bash
python3 skills/metadata/scripts/metadata.py init-source --backend tableau --source-id <source_id> --dry-run
python3 skills/metadata/scripts/metadata.py validate
python3 skills/metadata/scripts/metadata.py index
python3 skills/metadata/scripts/metadata.py search --type metric --query 收入
python3 skills/metadata/scripts/metadata.py context --dataset-id <dataset_id> --metric <metric>
python3 skills/metadata/scripts/metadata.py export-osi --model-name <model_name>
```

## 脚本归属

`RA:metadata` 相关脚本统一放在 `skills/metadata/scripts/`：

- `metadata.py`：统一命令入口。
- `init_metadata.py`：初始化 YAML 元数据样例和说明文件。
- `validate_metadata.py`：校验 YAML 维护契约。
- `build_index.py`：从 YAML 生成低 token JSONL 索引。
- `search_metadata.py`：检索 dataset、field、metric、term。
- `build_context.py`：生成分析规划用 context pack。
- `build_inventory.py`：生成当前元数据系统清单。
- `export_osi.py`：在交换场景把 YAML 导出为 OSI semantic model。

旧 `metadata-init`、`metadata-validate`、`metadata-index`、`metadata-search`、`metadata-context`、`metadata-inventory`、`osi-export` 目录不再保留可执行脚本或残留文件夹。

Tableau/DuckDB connector adapter 也从 `skills/` 顶层移入 `skills/metadata/adapters/`，避免继续表现为独立 sync skill。

## 产品边界

- 用户不需要判断该用 `tableau-sync` 还是 `duckdb-sync`。
- connector adapter 不单独决定业务口径。
- index 与 context pack 都不是维护真源。
- `needs_review=true` 的口径必须在分析、报告和验证里标记为推断口径。
