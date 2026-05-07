# 数据库与取数规范

> RealAnalyst 使用 SQLite 承接 runtime registry 和 metadata search index，使用 DuckDB 做受控分析取数。当前没有 ORM，也没有版本化 migration 框架。

---

## 数据层职责

三个“数据库式”层必须分开：

| 层 | 路径 | 职责 | 写入路径 |
| --- | --- | --- | --- |
| Runtime registry | `runtime/registry.db` | 运行态 source entries、specs、enums、source groups、lookup tables | `metadata sync-registry` 和 runtime helper |
| Metadata search index | `metadata/index/search.db` | dataset、field、metric、mapping、glossary 的 FTS5 检索层 | `metadata index` |
| Analytical DuckDB | 通常在 `examples/data/*.duckdb` 或用户 workspace 路径 | 被 `RA:data-export` 查询的数据源 | 外部 source registration / demo builder |

不要把 SQLite runtime table 当作业务定义真源。业务定义真源在 `metadata/dictionaries/*.yaml`、`metadata/mappings/*.yaml` 和 `metadata/datasets/*.yaml`。

---

## 运行态 registry

`runtime/registry.db` 是 canonical runtime DB，路径定义在 `runtime/paths.py`：

```python
RUNTIME_DB_PATH = RUNTIME_DIR / "registry.db"
```

Registry 代码应使用 `runtime/tableau/sqlite_store.py`。该 store 用 `CREATE TABLE IF NOT EXISTS` 初始化表，并在 schema 需要弹性时把 payload 以 JSON 保存：

```python
def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_db(conn)
    return conn
```

当前表：

- `metadata`
- `categories`
- `entries`
- `specs`
- `enums`
- `source_groups`

优先使用已有 helper：

- `save_entry(entry)`、`save_spec(spec)` 用于数据集 runtime 注册。
- `get_entry_by_source_id(source_id)`、`load_spec_by_entry_key(entry_key)` 用于受控 export。
- `save_enum_payload(enum_ref, payload)`、`load_allowed_values(enum_ref)` 用于运行态枚举。
- `save_source_group(group)`、`find_groups_by_source(source_id)`、`list_source_groups()` 用于多源分析支持。

除非确实没有对应 helper，否则不要在无关脚本里直接写 `registry.db`。需要新表时，先在 `sqlite_store.py` 增加窄 helper。

---

## 元数据到 registry 的同步路径

`skills/metadata/scripts/sync_registry.py` 是已校验 metadata YAML 写入 `runtime/registry.db` 的唯一受控路径。

稳定顺序：

```bash
python3 skills/metadata/scripts/metadata.py validate
python3 skills/metadata/scripts/metadata.py index
python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id> --dry-run
python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <dataset_id>
python3 skills/metadata/scripts/metadata.py status --dataset-id <dataset_id>
```

`sync_registry.py` 写入前会校验每个 dataset：

```python
raw = load_dataset_file(path)
errors = validate_dataset(raw, path=path)
if errors:
    results.append({"dataset_id": raw.get("id"), "status": "invalid", "errors": errors})
    continue
entry, spec = build_entry_and_spec(raw)
if not args.dry_run:
    save_entry(entry)
    save_spec(spec)
```

`build_entry_and_spec()` 把语义 YAML 转成 runtime 字段：

- `entry["source_backend"]` 来自 `dataset.source.connector`。
- `entry["fields"]` 来自字段 source name。
- `entry["semantics"]` 承载 grain、dimensions、time fields、适用/不适用场景和 review flag。
- `spec["dimensions"]`、`spec["measures"]`、`spec["metrics"]`、`spec["filters"]` 驱动 export validation。

不要在 report 或 export 脚本里绕过 validation，也不要独立拼 entry/spec 结构。

---

## 元数据检索 index

`metadata/index/search.db` 由 `skills/metadata/scripts/build_index.py` 生成，通过这些入口检索：

- `skills/metadata/scripts/search_metadata.py`
- `skills/metadata-search/scripts/search.py`
- `skills/metadata/lib/metadata_search.py`

`skills/metadata-search/scripts/search.py` 优先使用 FTS5；只有 `search.db` 不存在时才 fallback 到 JSONL：

```python
fts5_db = index_dir / "search.db"
if fts5_db.exists():
    matches = search_fts5(fts5_db, args.query, record_type=fts5_type, limit=args.limit)
else:
    records.extend(load_jsonl(index_dir / INDEX_FILES[t]))
```

Search index 只是检索层。若 search 结果暴露语义缺失或过期，先更新 YAML，再运行 `metadata.py validate` 和 `metadata.py index`。

---

## 查询模式（DuckDB）

受控 DuckDB export 位于 `skills/data-export/scripts/duckdb/export_duckdb_source.py`。

必须遵循：

- 通过 runtime registry 解析 source：`get_entry_by_source_id(source_id)`。
- 加载注册 spec：`load_spec_by_entry_key(entry["key"])`。
- 对 selected、filtered、grouped、aggregated、ordered 字段做注册字段校验。
- 用 `_quote_ident()` 引用 identifier。
- filter 和 date range 使用参数化值。
- DuckDB 以 `read_only=True` 打开。
- CSV 和 `duckdb_export_summary.json` 写入当前 job 目录。

真实模式：

```python
con = duckdb.connect(str(db_path), read_only=True)
cur = con.execute(sql, params)
rows = cur.fetchall()
```

禁止：

- 分析脚本直接拿 DuckDB 路径查询，绕过 registry source。
- export 未出现在 `entry["fields"]` 或注册 spec 中的字段。
- 把 filter value 拼进 SQL 字符串。
- export 临时或废弃对象；exporter 会拒绝以 `TEMP_` 或 `ToDrop_` 开头的对象名。

---

## 查询模式（SQLite）

SQLite helper 使用 `sqlite3.Row`、短事务和 `_json_dumps()` / `_json_loads()`：

```python
conn.execute(
    "INSERT OR REPLACE INTO specs(entry_key, display_name, updated, spec_json) VALUES (?, ?, ?, ?)",
    (entry_key, spec.get("display_name"), spec.get("updated"), _json_dumps(spec)),
)
conn.commit()
```

使用参数化 SQL，不要把用户可控值拼进 SQLite statement。

新增 runtime table 时：

- 在 `_init_db(conn)` 中初始化。
- 为脚本查询会用到的 lookup 字段加 index。
- 在 `sqlite_store.py` 暴露小 helper API。
- 返回 plain Python dict/list，让 CLI 脚本稳定输出 JSON。

---

## 迁移策略

当前没有版本化 migration framework。runtime store 通过幂等建表创建缺失表。`runtime/runtime_config_store.py` 和 `runtime/migrate_runtime_config_to_sqlite.py` 用于兼容旧 runtime config 模式，但当前 registry 以 SQLite 为准。

需要 schema 变化时：

1. 使用幂等 `CREATE TABLE IF NOT EXISTS` 或 ALTER-safe 路径。
2. 保持旧安装项目的 legacy reader 兼容。
3. runtime 行为变化时，更新 `tests/test_metadata_product_fixes.py`。
4. 避免 destructive rewrite 用户的 `runtime/registry.db`。

---

## 常见错误

- 把 runtime sample values 或 enum values 写进 dataset YAML，而不是 runtime registry 或 evidence 文件。
- 把旧 metadata report 当真源，而不是从 YAML 重新生成 index/context。
- 已有 export parse/validate helper 时，仍手写 SQL 字符串拼接。
- 修改 metadata YAML 后忘记运行 `metadata.py index`；需要 export-ready 状态时忘记运行 `metadata.py sync-registry`。
- 在 project-local 安装环境中，假设 `runtime/registry.db` 一定已经存在并可用于取数。
