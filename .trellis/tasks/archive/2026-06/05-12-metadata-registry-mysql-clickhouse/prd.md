# brainstorm: metadata registry channels mysql clickhouse

## Goal

优化 RealAnalyst metadata 注册渠道，在现有 DuckDB 和 Tableau 基础上增加 MySQL 与 ClickHouse 的注册和使用能力。目标不是新增平行 registry，而是把 MySQL / ClickHouse 作为新的 connector backend 接入统一 metadata -> runtime registry -> report/export 流程。

## What I already know

* 用户明确要求：现有注册渠道有 DuckDB 和 Tableau，需要增加 MySQL 和 ClickHouse 的使用。
* 当前 metadata CLI 的 `init-source` 只允许 `--backend tableau|duckdb`，并返回 adapter handoff plan。
* 当前 `sync-registry` 通过 `dataset.source.connector` 生成统一 runtime entry/spec，写入 `runtime/registry.db`。
* `runtime/registry.db` 是 canonical runtime DB；写入路径必须是 `metadata validate -> metadata index -> metadata sync-registry`。
* DuckDB / Tableau adapter 只负责 discovery/init material，不负责业务定义、不直接接管 Markdown report。
* 当前 `metadata/sync/` scaffold 只创建 `duckdb/` 和 `tableau/`。
* 当前 `metadata-report` connector CLI 只支持 `duckdb` 和 `tableau`，但 dataset-first report 已可读通用 dataset facts。
* 当前受控取数只有 DuckDB exporter 和 Tableau exporter。用户已确认 MySQL / ClickHouse 必须进入完整可用闭环，包括受控数据导出。
* `RA:data-export` wrapper 会写 `.meta/acquisition_log.jsonl` 和 `.meta/artifact_index.json`；当前审计脚本只内置 Tableau / DuckDB 摘要解析。
* `RA:getting-started` doctor 当前只探测 `yaml`、`duckdb`、`pandas` 依赖；完整闭环需要纳入 MySQL / ClickHouse export 依赖 readiness。

## Assumptions (temporary)

* MySQL / ClickHouse 应以 `source.connector: mysql|clickhouse` 进入 dataset YAML，不改变 dataset/mapping/dictionary 分层。
* MySQL / ClickHouse 的 discovery snapshot 应进入 `metadata/sync/mysql/` 和 `metadata/sync/clickhouse/`，原始 evidence 进入 `metadata/sources/`。
* 连接凭据不写入 dataset YAML，也不写入报告；应通过环境变量名、DSN ref 或 workspace-local ignored config 引用。
* MySQL / ClickHouse exporter 应尽量复用 DuckDB exporter 的安全模型：registry source lookup、registered-field whitelist、参数化查询、job artifact summary。

## Open Questions

* 无阻塞问题。用户已选择完整闭环。

## Requirements (evolving)

* 保持职责独立：adapter 只产出 discovery/init material，metadata YAML 仍是语义真源，runtime registry 只承接可执行 source/spec。
* 扩展 `metadata init-source --backend` 支持 `mysql` 和 `clickhouse`。
* 扩展 `metadata/sync/` 初始化与文档，新增 MySQL / ClickHouse 目录和 README。
* 扩展 `sync_registry.py` 对 MySQL / ClickHouse connector 的 entry type、payload normalization、spec 写入。
* 扩展 `status_registry.py` 的 export-ready 判断，避免 MySQL / ClickHouse 永远只落到通用 `fields` 判断。
* 扩展 metadata report 对 MySQL / ClickHouse 的 connector label、技术行、边界说明。
* 新增 MySQL / ClickHouse discovery adapter，至少支持 schema/table/column introspection，输出 catalog snapshot 到 `metadata/sync/<connector>/`。
* 新增 MySQL / ClickHouse 受控 exporter：从 runtime registry 读取 source/spec，校验字段，参数化 SQL 查询，输出 CSV 和 `<connector>_export_summary.json`。
* 新增 MySQL / ClickHouse wrapper：调用直接 exporter 后写 acquisition log、artifact index、context injection。
* 扩展 `scripts/log_acquisition.py` 与 `scripts/update_artifact_index.py`，支持通用 SQL connector summary 或 MySQL / ClickHouse summary。
* 扩展 `RA:data-export` 文档和帮助，用户能从 registry 查询 source 后进入 MySQL / ClickHouse 后端流程。
* 扩展 dependency setup / doctor readiness，清晰提示缺少 MySQL / ClickHouse Python client 时的修复命令。
* 增加覆盖 MySQL / ClickHouse 的测试，避免只写文档不打通 CLI。

## Acceptance Criteria (evolving)

* [ ] `python3 skills/metadata/scripts/metadata.py init-source --backend mysql --source-id <id> --dry-run` 输出明确 adapter plan。
* [ ] `python3 skills/metadata/scripts/metadata.py init-source --backend clickhouse --source-id <id> --dry-run` 输出明确 adapter plan。
* [ ] MySQL / ClickHouse dataset YAML 可通过 `metadata validate`。
* [ ] MySQL / ClickHouse dataset YAML 可通过 `metadata sync-registry --dry-run` 生成 connector-aware entry/spec。
* [ ] `metadata status --dataset-id <id>` 对 MySQL / ClickHouse 给出合理 registry/export-ready 状态。
* [ ] `metadata-report` 或 dataset-first report 能展示 MySQL / ClickHouse connector，不出现 DuckDB/Tableau 专属误导说明。
* [ ] MySQL / ClickHouse discovery adapter 的 `--help` 和 dry-run/snapshot contract 可测，不依赖真实远端数据库。
* [ ] MySQL / ClickHouse exporter 能基于测试替身或 mock connection 验证：字段白名单、filter/date-range/group-by/aggregate/order-by、参数化查询、CSV 输出、summary 输出。
* [ ] MySQL / ClickHouse wrapper 能写 acquisition log、artifact index、latest summary 和 context injection。
* [ ] `RA:data-export` 文档列出 MySQL / ClickHouse 推荐入口、直接入口、安全边界和输出契约。
* [ ] 新增或更新测试覆盖 CLI、registry sync、status、report、scaffold/docs、export wrapper、audit artifacts。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 不把 MySQL / ClickHouse 的 sample values、enum values、schema snapshot 复制进 `metadata/datasets/*.yaml`。
* 不新建用户可见 `mysql-*` 或 `clickhouse-*` metadata skill 取代 `RA:metadata`。
* 不把连接密码、token、DSN 明文写入 metadata YAML、runtime report 或 git-tracked examples。
* 不引入 destructive migration 或重写已有用户 `runtime/registry.db`。
* 不在分析脚本中自由连接 MySQL / ClickHouse；正式取数必须从已注册 runtime source 进入。
* 不在第一版实现跨库 join、跨 source federation 或任意 SQL 执行入口。

## Technical Notes

* Current CLI: `skills/metadata/scripts/metadata.py`
* Registry sync: `skills/metadata/scripts/sync_registry.py`
* Registry status: `skills/metadata/scripts/status_registry.py`
* Runtime store: `runtime/tableau/sqlite_store.py`
* Current scaffold: `skills/metadata/scripts/init_metadata.py`
* Connector boundary doc: `skills/metadata/references/connector-adapters.md`
* Report entry: `skills/metadata-report/scripts/generate_report.py`
* Report context: `skills/metadata-report/scripts/report_context.py`
* Data export skill: `skills/data-export/SKILL.md`, `skills/data-export/README.md`
* DuckDB exporter pattern: `skills/data-export/scripts/duckdb/export_duckdb_source.py`, `skills/data-export/scripts/duckdb/duckdb_export_with_meta.py`
* Job audit scripts: `scripts/log_acquisition.py`, `scripts/update_artifact_index.py`
* Environment doctor: `skills/getting-started/scripts/doctor.py`
* Backend specs reviewed: `.trellis/spec/backend/directory-structure.md`, `.trellis/spec/backend/database-guidelines.md`

## Expansion Sweep

### Future evolution

* 多 connector 后，registry 需要保持 connector payload 可扩展，避免每加一个数据库都改一堆硬编码。
* 未来可能需要统一 SQL export base，而不是每种数据库复制一份 exporter。

### Related scenarios

* `metadata init`、`metadata init-source`、`metadata status`、`metadata-report`、`data-export` 的 connector 命名必须一致。
* project-local 安装布局也要工作，不能只在源码仓路径下可运行。

### Failure & edge cases

* 凭据缺失时应报告配置缺口，不应在 report 里泄露 secret。
* ClickHouse / MySQL schema discovery 可能需要网络连接；dry-run 和 example tests 不能依赖真实外网数据库。
* registry 中已存在同 dataset id 时仍走 `save_entry/save_spec` 的 upsert 路径，不手写 DB。

## Technical Approach Options

**Approach A: Registry-first connector support** (Recommended for MVP)

* How: 支持 MySQL / ClickHouse 的 `init-source`、scaffold、registry sync/status、report，adapter discovery 先用 handoff plan 和 snapshot contract，不实现真实数据库连接取数。
* Pros: 快速打通 metadata 注册主链路，风险低，不引入凭据和网络依赖。
* Cons: 还不能直接通过 RealAnalyst 从 MySQL / ClickHouse 导出数据。

**Approach B: Registration + discovery adapters**

* How: 在 Approach A 基础上增加 MySQL / ClickHouse schema discovery 脚本，输出 catalog snapshot，但不做正式 export。
* Pros: 注册素材更自动，适合实际接入数据库。
* Cons: 需要确定依赖库、连接参数、凭据管理和测试替身。

**Approach C: Full runtime export support**

* How: 在 Approach B 基础上新增受控 MySQL / ClickHouse exporter，按 registry spec 校验字段、参数化 SQL、写 job artifact summary。
* Pros: 真正完成“注册后可用”闭环。
* Cons: 范围更大，需要更多安全、SQL 方言和依赖测试。

## Decision (ADR-lite)

**Context**: 用户明确要求“完整可用闭环”，不是只把 MySQL / ClickHouse 名字加进注册渠道。

**Decision**: 采用 Approach C。MySQL / ClickHouse 接入范围包括 discovery adapter、metadata registration、runtime registry sync/status、metadata report、controlled data export、job audit artifacts、docs/tests。

**Consequences**:

* 范围会跨 `RA:metadata`、`RA:metadata-report`、`RA:data-export`、runtime helper、doctor、docs/tests。
* 需要新增数据库 client 依赖或可选依赖检查；测试不能依赖真实远端数据库。
* SQL 安全边界必须明确：只允许 registry/spec 中注册字段；所有 filter/date parameters 参数化；不提供任意 SQL 输入。
* MySQL / ClickHouse 真实凭据不能进入 git-tracked metadata；runtime payload 只保存 host/database/schema/table 等非敏感定位信息和 credential reference。

## Impact Analysis

### 1. Metadata CLI and scaffold

Affected files:

* `skills/metadata/scripts/metadata.py`
* `skills/metadata/scripts/init_metadata.py`
* `metadata/sync/README.md`
* new `metadata/sync/mysql/README.md`
* new `metadata/sync/clickhouse/README.md`

Impact:

* `init-source --backend` choices 从 `tableau|duckdb` 扩到 `tableau|duckdb|mysql|clickhouse`。
* `adapter_plan()` 要返回对应 discovery / inspect / export handoff scripts。
* `metadata init` 需要创建 `metadata/sync/mysql` 和 `metadata/sync/clickhouse`。
* sync README 要说明真实 catalog snapshot 不提交，脱敏 example 可以提交。

### 2. Connector adapters

Affected files:

* `skills/metadata/references/connector-adapters.md`
* new `skills/metadata/adapters/mysql/scripts/*`
* new `skills/metadata/adapters/clickhouse/scripts/*`

Impact:

* 新增 MySQL / ClickHouse adapter boundary：只负责 discovery/init material，不负责业务口径、不直接写业务定义。
* Discovery output 建议统一成 catalog JSON：connector、source_id、host ref、database、schema、table/view、columns、types、nullable、row count estimate、sample/profile path。
* Adapter 不写 `metadata/datasets/*.yaml` 的业务定义，只把原始输出归档为 evidence。

### 3. Runtime registry sync/status

Affected files:

* `skills/metadata/scripts/sync_registry.py`
* `skills/metadata/scripts/status_registry.py`
* possibly `runtime/tableau/sqlite_store.py` only if a narrow helper is needed

Impact:

* `_connector_type()` 增加 `mysql_table/mysql_view`、`clickhouse_table/clickhouse_view`。
* `_connector_payload()` 增加 MySQL / ClickHouse payload normalization，例如 `database`、`schema`、`table`、`object_name`、`credential_ref`、`connection_ref`。
* `status_registry.py` export-ready 对 MySQL / ClickHouse 应检查：connector payload、object/table、registered fields、credential/connection reference，不要求真实连接成功。
* 不新增 registry table，继续通过 entry/spec JSON payload 承接 connector-specific metadata。

### 4. Metadata report

Affected files:

* `skills/metadata-report/scripts/generate_report.py`
* `skills/metadata-report/scripts/report_context.py`
* possibly connector-specific wrapper/report tests

Impact:

* `--connector` choices 可扩到 `duckdb|tableau|mysql|clickhouse`，或优先收敛到 dataset-first report 并让 connector label 通用化。
* Report context 要展示 MySQL / ClickHouse 技术行：database/schema/table、connection_ref、object_kind。
* 删除 DuckDB/Tableau 专属误导：MySQL / ClickHouse 不应出现 “DuckDB 示例值边界” 或 “Tableau 参数边界”。
* 报告中不得展示 password/token/DSN plaintext。

### 5. Data export and job artifacts

Affected files:

* `skills/data-export/SKILL.md`
* `skills/data-export/README.md`
* new `skills/data-export/scripts/mysql/export_mysql_source.py`
* new `skills/data-export/scripts/mysql/mysql_export_with_meta.py`
* new `skills/data-export/scripts/clickhouse/export_clickhouse_source.py`
* new `skills/data-export/scripts/clickhouse/clickhouse_export_with_meta.py`
* `scripts/log_acquisition.py`
* `scripts/update_artifact_index.py`
* `skills/data-profile/scripts/run.py` if latest-summary discovery must become generic

Impact:

* Exporter 需要复用安全行为：registry lookup、active source check、field whitelist、参数化 SQL、registered aggregate whitelist。
* Summary contract 建议统一为 `<connector>_export_summary_<output-name>_<timestamp>.json` 和 `<connector>_export_summary.json`。
* `log_acquisition.py` 可以新增 `--from-sql-summary` 或分别支持 `--from-mysql-summary` / `--from-clickhouse-summary`。推荐通用 SQL summary，避免继续复制 DuckDB 分支。
* `update_artifact_index.py` 同样推荐通用 SQL summary ingestion。
* `data-profile` 当前优先读取 `export_summary.json` / `duckdb_export_summary.json`；完整闭环最好扩展为读取 connector-neutral `data_export_summary.json`，同时保留旧 summary 兼容。

### 6. Dependencies and environment readiness

Affected files:

* `requirements.txt`
* `scripts/setup_venv.sh`
* `skills/getting-started/scripts/doctor.py`
* installer docs if dependency behavior changes

Impact:

* 需要决定依赖方案：直接加入 `pymysql` / `clickhouse-connect`，或 optional dependency with clear remediation。
* Doctor 需要探测 `pymysql`、`clickhouse_connect`，并在 export/analyze 场景给出缺依赖提示。
* Tests 应 mock client import/connection，避免 CI 需要真实 MySQL / ClickHouse 服务。

### 7. Tests and quality gates

Affected files:

* `tests/test_metadata_product_fixes.py`
* possibly new focused test files if split becomes clearer
* `skills/data-export/scripts/*/run_tests.py` if backend-specific smoke tests are added

Impact:

* 需要覆盖 CLI parser choices、adapter plan、scaffold dirs、registry sync entry/spec、status readiness、report context、安全字段校验、summary generation、audit artifact ingestion。
* 不能只加文档和 README；至少要有 unit-level tests 证明 MySQL / ClickHouse 的 closed loop 路径能被程序识别。

### 8. Documentation and user-facing routing

Affected files:

* `README.md`
* `skills/README.md`
* `skills/metadata/SKILL.md`
* `skills/metadata/README.md`
* `skills/data-export/SKILL.md`
* `skills/data-export/README.md`
* `docs/metadata-lookup-workflow.md`
* `docs/architecture.md`
* `docs/skill-interaction-design.md`
* `docs/update-guide.md`

Impact:

* 所有 “Tableau / DuckDB” 的用户可见说法要改成 “Tableau / DuckDB / MySQL / ClickHouse” 或 “registered connectors”，避免遗漏。
* 仍保持普通用户入口收口：用户先用 `RA:metadata` 注册，再由 `RA:analysis-run` 编排 `RA:data-export`。
* 文档要强调 MySQL / ClickHouse 凭据不进 metadata YAML，不在报告中展示 secret。

## Implementation Plan

### PR1: Connector foundation and metadata registration

* Add `mysql` / `clickhouse` to `metadata init-source`.
* Add scaffold directories and README files under `metadata/sync/`.
* Extend `sync_registry.py` payload/type normalization.
* Extend `status_registry.py` readiness checks.
* Add tests for metadata CLI, scaffold, registry sync/status.

### PR2: Discovery adapters and report support

* Add MySQL / ClickHouse adapter script skeletons with `--help`, connection args, dry-run and catalog snapshot output contract.
* Update `connector-adapters.md`.
* Extend metadata report labels, technical rows and boundary text.
* Add tests for report context and no-secret rendering.

### PR3: Controlled SQL export core

* Add common SQL export helper or small shared utility for parsing select/filter/date/group/aggregate/order clauses.
* Add MySQL and ClickHouse direct exporters.
* Enforce registered field whitelist, active source, parameterized SQL, output CSV and summary JSON.
* Add mock-based tests for SQL construction, field validation, summary generation.

### PR4: Export wrappers and job audit artifacts

* Add MySQL / ClickHouse wrapper scripts.
* Extend `log_acquisition.py` and `update_artifact_index.py` using a generic SQL summary path.
* Add or migrate to connector-neutral `data_export_summary.json` while preserving existing Tableau / DuckDB summary compatibility.
* Extend `data-profile` summary discovery if needed.
* Add tests for wrapper audit artifacts and artifact index.

### PR5: Docs, doctor and release readiness

* Add dependencies/remediation in `requirements.txt`, `setup_venv.sh`, `doctor.py`.
* Update README/SKILL docs and architecture docs.
* Run quality gates: targeted tests, full relevant test file, `git diff --check`, compile/help smoke.

## Rollout / Rollback

* Rollout can be staged by connector: land MySQL first, then ClickHouse, but keep shared contract stable.
* Existing DuckDB/Tableau registry entries must remain valid; tests should assert no behavior regression for current connectors.
* Rollback is low-risk if changes are additive and no registry migration is required. Removing new scripts and connector choices should not corrupt existing `runtime/registry.db`.
