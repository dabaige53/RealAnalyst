# Connector Adapters

connector adapter 是 metadata skill 的内部能力，不是用户优先选择的入口。

## Tableau Adapter

Tableau adapter 负责：

- 发现 workbook、view、dashboard 候选对象。
- 抽取 Tableau 字段、筛选器、参数和样例值。
- 为 metadata YAML 提供初始化素材。
- 在需要执行 Tableau 导出时保留运行所需 source 信息。

Tableau adapter 不负责：

- 单独决定业务指标口径。
- 维护最终业务定义。
- 替代 metadata YAML。
- 手工从 YAML 覆盖 `registry.db`；运行层只能通过 `metadata sync-registry` 受控 upsert。

### Tableau adapter scripts

```bash
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/discover.py --workbook <workbook_name>
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/sync_fields.py --key <entry_key>
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/sync_filters.py --source-key <entry_key> --with-samples
```

将这些脚本输出视为素材。LLM 必须先把原始输出归档到 `metadata/sources/`，再把字段映射维护到 `metadata/mappings/*.yaml`，把真实数据源字段、筛选器、业务说明、证据和 review 标记维护到 `metadata/datasets/*.yaml`。

报告不由 Tableau adapter 生成；同步完成后调用 `RA:metadata-report` 的 `skills/metadata-report/scripts/generate_report.py` 输出 Markdown。

## DuckDB Adapter

DuckDB adapter 负责：

- 读取 DuckDB catalog、schema、table、view 和 column 信息。
- 抽取字段类型、行数、时间字段、数值字段和候选维度。
- 为 metadata YAML 提供初始化素材。
- 在需要执行 DuckDB 查询时保留运行所需 source 信息。

DuckDB adapter 不负责：

- 单独决定业务指标口径。
- 维护最终业务定义。
- 替代 metadata YAML。
- 手工从 YAML 覆盖 `registry.db`；运行层只能通过 `metadata sync-registry` 受控 upsert。

### DuckDB adapter scripts

```bash
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/discover_catalog.py --registerable-only
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/inspect_source.py --source <source_id>
```

将这些脚本输出视为素材。LLM 必须先把原始输出归档到 `metadata/sources/`，再把字段映射维护到 `metadata/mappings/*.yaml`，把真实数据源字段、粒度、时间字段、指标候选、限制和 review 标记维护到 `metadata/datasets/*.yaml`。

报告不由 DuckDB adapter 生成；同步完成后调用 `RA:metadata-report` 的 `skills/metadata-report/scripts/generate_report.py` 输出 Markdown。

## MySQL / ClickHouse Adapter

MySQL 和 ClickHouse adapter 负责：

- 读取数据库、schema/table/view 和 column catalog。
- 生成可归档到 `metadata/sync/mysql/` 或 `metadata/sync/clickhouse/` 的结构快照。
- 为 `metadata/datasets/*.yaml` 的字段、物理对象、连接引用提供初始化素材。
- 保留受控导出所需的非敏感定位信息，例如 `database`、`schema`、`table`、`connection_ref`。

MySQL 和 ClickHouse adapter 不负责：

- 单独决定业务指标口径。
- 维护最终业务定义。
- 将 sample/profile/column snapshot 复制进 dataset YAML。
- 写入密码、token、DSN 明文或手工覆盖 `runtime/registry.db`。

### MySQL / ClickHouse adapter scripts

```bash
python3 {baseDir}/skills/metadata/adapters/mysql/scripts/discover_catalog.py --source-id <dataset_id> --database <database> --table <table> --dry-run
python3 {baseDir}/skills/metadata/adapters/clickhouse/scripts/discover_catalog.py --source-id <dataset_id> --database <database> --table <table> --dry-run
```

真实 discovery 需要通过 `--connection-ref`、`--credential-ref` 或 `--dsn-env` 指向环境变量中的连接配置。脚本输出是 evidence/material；正式可取数状态只能通过 `metadata validate -> metadata index -> metadata sync-registry -> metadata status` 进入 runtime registry。

## 调用原则

用户请求“注册数据集”“初始化元数据”“维护字段/指标口径”时，先使用 metadata skill。只有 metadata skill 明确需要连接 Tableau、DuckDB、MySQL 或 ClickHouse 时，才调用对应 adapter 脚本。

## 禁止事项

- 不新增 `tableau-*`、`duckdb-*`、`mysql-*` 或 `clickhouse-*` 用户可见 skill 来承接元数据维护。
- 不让 adapter 直接成为业务定义的真源。
- 不把 adapter 结果直接写成确定口径。
- 不手工覆盖 `registry.db`；需要进入运行层时使用 `metadata sync-registry`。
