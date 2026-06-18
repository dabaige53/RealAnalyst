# 日志与输出规范

> RealAnalyst 当前没有统一 Python logging framework。脚本主要通过 JSON stdout、简短状态行、append-only JSONL 审计文件和 Markdown report 与 agent/用户沟通。

---

## 输出模型

按受众选择输出通道：

| 通道 | 受众 | 真实示例 |
| --- | --- | --- |
| JSON stdout | agent / 脚本调用方 | `metadata.py list-commands`、`sync_registry.py`、`skills/data-profile/scripts/run.py`、`skills/metadata-search/scripts/search.py` |
| 简短状态行 | 人类操作者 | `scripts/install_codex_plugin.py`、`skills/metadata-report/scripts/generate_report.py` |
| 追加式 JSONL audit | job lineage / metadata 维护追踪 | `scripts/log_acquisition.py`、`metadata/audit/metadata_changes.jsonl`、`metadata/audit/metadata_relations.jsonl` |
| Markdown report | 用户复核 | `metadata/audit/metadata_change_report.md`、`metadata/sync/*/reports/*.md` |

不要向 stdout 被 JSON parser 消费的脚本加入 debug 行。

---

## 结构化 stdout（JSON）

当命令会被另一个 skill 或测试调用时，stdout 在成功时应是合法 JSON，在预期失败时也应是结构化 JSON。

示例：

- `skills/metadata/scripts/sync_registry.py` 输出 `success`、`dry_run`、`registry_db` 和 per-dataset `results`。
- `skills/metadata-search/scripts/search.py` 输出 `success`、`query`、`type`、`backend` 和 `matches`。
- `skills/data-profile/scripts/run.py` 输出 profile result 或结构化 error object。

如果底层函数会打印诊断信息，先捕获，再输出最终 JSON。`skills/data-profile/scripts/run.py` 用 `redirect_stdout(log_buffer)` 包住 `profile_data()`，确保 wrapper 的 stdout 干净。

---

## 人类状态行

只有不会被机器解析 stdout 的命令才输出简短状态行。

当前模式：

- `skills/metadata-report/scripts/generate_report.py` 输出 `[OK] report -> <path>`。
- 没有匹配目标时输出 `[WARN] No DuckDB entries matched`。
- metadata 校验失败时输出 `[Error] metadata validate failed:`。
- `scripts/install_codex_plugin.py` 输出 `$ copytree <source> -> <target>` 和最终安装摘要。

状态行要具体、路径导向，不要从 library function 打进度 banner。

---

## 审计日志

事件 lineage 使用 append-only JSONL：

- `scripts/log_acquisition.py` 追加 acquisition events 到 `.meta/acquisition_log.jsonl`。
- `skills/metadata/scripts/metadata.py record-change` 委托 `metadata_audit.py`，更新 `metadata/audit/metadata_changes.jsonl`。
- `metadata.py record-relation` 把 `business_definition.ref` 关系写入 `metadata/audit/metadata_relations.jsonl`。

审计记录应包含足够上下文：

- source backend 或 dataset id。
- output path 或 changed metadata path。
- timestamp。
- reason / summary。
- relevant confirmation flags。

正常操作中不要重写历史审计记录。

---

## 应输出什么

应该输出或记录：

- 生成 artifact、report、summary 的路径。
- dataset id / source id / connector scope。
- 带准确 metadata key path 的 validation errors / warnings。
- Registry sync 状态：`preview`、`synced`、`invalid`。
- Export lineage：source id、selected fields、filters、date ranges、row count、summary file。
- 输出来源：来自 `export_summary`、`duckdb_export_summary` 还是显式用户输入。
- 缺依赖信息和安装命令。

---

## 禁止输出什么

不要输出：

- credentials、tokens、Tableau passwords、API keys、cookies、`.env` values。
- 完整敏感 source files 或原始业务数据集。
- 用户机密文档，除非它们被有意归档为 `metadata/sources/` evidence。
- 正常日志中的整行 CSV 数据。
- 编造的占位行或泛化提醒。
- 普通分析用户回复、报告正文、README“用户会得到什么”、Completion Summary 默认不要展示本地路径、内部目录、脚本名、系统 JSON 文件名、source key、dataset id、profile 文件或审计日志。

Sample values 只可用于识别值域或格式，不是完整枚举，也不是业务定义。

用户态输出分层：

- 用户可见：业务摘要、可见交付物名称、验证状态、主要风险、下一步动作。
- 内部审计：job manifest、artifact index、profile manifest、verification JSON、analysis journal、source context、metadata index、archive recovery index。
- 技术详情：只有用户明确要求排障/开发/PR/测试，或报告使用受控技术详情标记时，才输出最小必要路径、脚本名和系统文件名。

`skills/*/SKILL.md` 的 `## Completion Summary` 默认按用户可见层写。需要说明内部登记时，用“内部登记已完成”“验证状态已同步”这类业务可读表述；不要在普通总结里列 `job_manifest.json`、`verification.json`、`.meta/`、`profile/manifest.json` 等文件名。

---

## 状态词汇

当前没有 `logging` module level policy。打印状态行时使用这些词：

- `[OK]` 表示输出完成，并附路径。
- `[WARN]` 表示非致命的 no-target / no-sample / no-match。
- `[Error]` 表示 validation 或 CLI mode failure，命令停止。

不要引入第二套状态词，除非整个项目统一迁到标准 `logging` module。

---

## 脚本 stdout 契约

每个脚本只能选择一种 stdout contract：

1. JSON-only stdout。
2. Human status stdout。
3. Generated file path / status stdout。

不要把 JSON payload 和人类进度行混在同一个命令中，除非现有脚本已经是这种 contract 且没有调用方解析 stdout。

当 wrapper 调用 noisy function 时，redirect 或 suppress 内部 stdout，再输出一个最终 JSON payload。这样比让调用方从混合输出中解析更稳。

如果 wrapper 需要保留内层脚本结果，应解析内层 JSON 并合并到外层 JSON 字段中；不得把两个 JSON object 依次打印到 stdout。测试应至少做一次 `json.loads(stdout)`。

---

## Dataset-first metadata report 契约

### 1. Scope / Trigger

当修改 `RA:metadata-report`、`metadata.py read`、metadata search/read helper 或 runtime registry 事实展示时，必须按本契约检查。这个路径面向“准备使用数据做分析的人”，报告只呈现已维护事实，不生成业务推断、不改写 metadata 原文、不产生第二套 context。

### 2. Signatures

推荐入口：

```bash
python3 skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id>
python3 skills/metadata-report/scripts/generate_report.py --all
python3 skills/metadata-report/scripts/generate_report.py --dataset-id <dataset_id> --output-dir <dir>
python3 skills/metadata/scripts/metadata.py read --dataset-id <dataset_id>
python3 skills/metadata/scripts/metadata.py read --all
```

兼容入口可以保留 `--connector`，但 README、SKILL 和模板应优先推荐 dataset-first 命令。

### 3. Contracts

- `metadata.py read` stdout 是 JSON-only，成功时包含 `success: true` 和 `results[]`。
- `generate_report.py` dataset-first stdout 是 human status，成功时输出 `[OK] report -> <path>`。
- 默认报告路径是 `metadata/reports/<dataset_id>_metadata_report.md`，重复生成覆盖最新版。
- Dataset-first report 不生成 `*_metadata_context.json` 或其它 machine context sidecar。
- 报告事实通过 metadata read/search/status helper 进入 renderer；report 层只做展示编排。
- 报告不得读取 `jobs/*/profile/*`、不得调用 `RA:data-profile`、不得现场查 DuckDB 或采样。
- 标题、表头、状态标签使用中文；metadata 原始值保持原样。
- 数值字段只展示已维护范围，日期字段只展示已维护起止，文本/分类字段才展示已维护取值列表。缺失时写 `未维护`；registry 缺失时写 `未注册`。

### 4. Validation & Error Matrix

| 条件 | 行为 |
| --- | --- |
| dataset 不存在或 metadata read 失败 | `metadata.py read` 返回 `success: false`、稳定 `error_code`，report 命令失败 |
| index JSONL / search payload 损坏 | 转成可见 metadata read failure，不静默生成 partial report |
| registry 不存在或 dataset 未注册 | report 继续生成，对应状态写 `未注册` |
| 字段/指标定义缺失 | report 继续生成，单元格写 `未维护` |
| 整个 section 无真实内容 | 不输出空 section，把缺口汇总到“未维护项” |
| 用户误用 connector-only 参数但未指定 connector | 返回 CLI misuse，不把兼容模式当 dataset-first 执行 |

### 5. Good/Base/Bad Cases

- Good: dataset 有 YAML、index、runtime registry 和取值范围，报告输出中文章节、来源列和已维护范围。
- Base: dataset 只有 YAML，没有 registry，报告仍输出字段/指标事实，并把运行状态写为 `未注册`。
- Bad: dataset 不存在，命令返回结构化失败，不能生成占位 Markdown。

### 6. Tests Required

修改 dataset-first report 或 `metadata.py read` 时，至少覆盖：

- `metadata.py read --dataset-id` 成功和 dataset missing 失败。
- `generate_report.py --dataset-id` 默认输出路径、覆盖行为、无 JSON sidecar。
- `generate_report.py --all --output-dir`。
- job profile 内容不会泄漏到 metadata report。
- 数值/日期字段不展示枚举列表，缺范围时 `未维护`。
- 文本/分类字段保留已维护取值列表。

### 7. Wrong vs Correct

#### Wrong

```text
字段 role=dimension，所以报告写“适合按该字段做经营分析”；数值字段有 sample_values，所以列出 2021、2022。
```

#### Correct

```text
报告只列 metadata / registry 已维护事实。没有用途原文就不写用途；数值字段没有 min/max 范围就写“未维护”。
```

---

## 常见错误

- JSON 前打印 debug 行，导致 `json.loads(proc.stdout)` 测试失败。
- 每个字段/指标都打日志；多数场景只需要 summary count 和 report path。
- 在 metadata report 中重复 generic usage note，而不是报告具体 gap。
- 把 sample 当成完整 enum 输出。
- 把生成路径藏在 prose 里，而不是放进 JSON 或清晰的 `[OK] report ->` 状态行。
