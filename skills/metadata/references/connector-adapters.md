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
- 从 YAML 反写覆盖 `registry.db`。

### Tableau adapter scripts

```bash
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/discover.py --workbook <workbook_name>
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/sync_fields.py --key <entry_key>
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/sync_filters.py --source-key <entry_key> --with-samples
python3 {baseDir}/skills/metadata/adapters/tableau/scripts/generate_sync_report.py --source-key <entry_key>
```

将这些脚本输出视为素材。LLM 必须把确认后的字段、筛选器、业务说明、证据和 review 标记维护回 `metadata/datasets/*.yaml`。

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
- 从 YAML 反写覆盖 `registry.db`。

### DuckDB adapter scripts

```bash
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/discover_catalog.py --registerable-only
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/inspect_source.py --source <source_id>
python3 {baseDir}/skills/metadata/adapters/duckdb/scripts/generate_sync_report.py --source <source_id>
```

将这些脚本输出视为素材。LLM 必须把确认后的字段、粒度、时间字段、指标候选、限制和 review 标记维护回 `metadata/datasets/*.yaml`。

## 调用原则

用户请求“注册数据集”“初始化元数据”“维护字段/指标口径”时，先使用 metadata skill。只有 metadata skill 明确需要连接 Tableau 或 DuckDB 时，才调用对应 adapter 脚本。

## 禁止事项

- 不新增 `tableau-*` 或 `duckdb-*` 用户可见 skill 来承接元数据维护。
- 不让 adapter 直接成为业务定义的真源。
- 不把 adapter 结果直接写成确定口径。
- 不通过 YAML 反写覆盖 `registry.db`。
