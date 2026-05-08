# 质量规范

> RealAnalyst 的质量标准围绕“职责边界清楚、metadata 分层不污染、命令输出可被 agent 消费、真实验证可复跑”展开。不要用泛化模板替代当前仓库的真实检查。

---

## 基本原则

- 改动要小而准，只触碰用户请求相关文件。
- 优先使用已有 helper、script 和 skill contract，不新增旁路入口。
- 修改 metadata 语义、runtime registry、report 生成、installer 或 skill 目录时，同步检查 README、SKILL.md、脚本入口和测试。
- 修改 skill routing、installer 或 public docs 时，必须检查普通用户入口仍是 3 个主入口 + 3 个常见补充入口，流程内/高级/兼容 skill 不得重新平铺到第一层。
- 修改正式任务入口或流程内 skill 时，必须保持 `RA:getting-started` doctor 作为环境摘要入口；不要让下游 skill 通过自由 `which/find/python3/duckdb/sqlite3` 自行发现或绕过项目环境。
- 修改 `skills/*/SKILL.md` 时，必须保持唯一 `## Completion Summary`，并包含“完成情况 / 下一步建议 / 边界提醒”三段轻量交接。
- 不为了修一个输出问题 hard-code 某个业务字段名、指标名或固定中文列名；报告逻辑必须按 metadata 结构、role、definition、expression、mapping、evidence 等通用规则处理。
- 没有真实数据、真实 metadata、真实 connector 输出或真实 evidence 时，不生成占位内容撑版面。

---

## 必跑检查

按改动类型选择最小但真实的检查。

| 改动类型 | 检查 |
| --- | --- |
| Python 脚本语法或导入路径 | `python3 -m py_compile <changed_script.py>` |
| metadata YAML / validation 逻辑 | `python3 skills/metadata/scripts/metadata.py validate`，必要时加 `--completeness` |
| metadata index / search 逻辑 | `python3 skills/metadata/scripts/metadata.py index`，再跑相关 search smoke |
| runtime registry sync | `python3 skills/metadata/scripts/metadata.py sync-registry --dataset-id <id> --dry-run`，需要落库时再正式 sync |
| metadata report 逻辑 | 运行对应 `skills/metadata-report/scripts/generate_report.py` 或 connector report 脚本，并检查没有占位内容或泛化提醒 |
| DuckDB export | 使用 `skills/data-export/scripts/duckdb/run_tests.py` 或最小 export smoke |
| release / installer | `python3 scripts/check_release_alignment.py --allow-network-failure`，并检查 `scripts/install_codex_plugin.py` 的 dry-run 或 smoke path |
| 全仓回归 | `python3 -m pytest tests/test_metadata_product_fixes.py` |

CI 里已有 `.github/workflows/ci.yml` 运行 `python skills/metadata/scripts/metadata.py validate`。不要把本地未通过的 metadata validation 留给 CI。

---

## 测试约定

当前测试集中在 `tests/test_metadata_product_fixes.py`。新增或修改以下行为时，优先补这个文件的 focused tests：

- dataset responsibility boundary：禁止 `sample_profile`、`enum_values`、`source_mapping`、`source_evidence` 等泄漏进 dataset YAML。
- dataset identity boundary：禁止把 CSV/header/display name 中文化写回 `fields[].name` 或 `metrics[].name`。
- `description` 与 `business_definition.text` 重复检测。
- pending definition 不得注册为 formal metric。
- 大 YAML 行数 warning/fail gate。
- `metadata validate --completeness` 对 metric mapping gap 的检测。
- report 生成缺内容时降级为待修复清单，而不是写确定口径。
- DuckDB export 对 registry spec、字段、filter、order、aggregate 的校验。
- project-local `.agents/skills` 安装布局兼容。

测试 fixture 应使用临时 workspace，例如现有测试中的 `tempfile.TemporaryDirectory()` 和 `write_dataset()`。不要依赖用户本机真实业务数据。

---

## 禁止模式

- 在 `metadata/datasets/*.yaml` 中复制 profile、sample values、enum、mapping、registry snapshot、report 结论或证据全文。
- 直接手工编辑 `metadata/index/`、`metadata/osi/` 这类生成层。
- report 逻辑按具体字段名打特例补丁。
- role/status 自动生成“使用建议”“常见用途”等无 evidence 的文案。
- validation 失败仍继续输出确定业务口径。
- stdout 既输出 JSON 又夹杂 debug/progress 行。
- 用 string 拼接 SQL filter value。
- 修改 installer、skill list 或 public docs 时漏掉 mirrored README / INSTALL / plugin metadata。
- 把 `RA:data-export`、`RA:data-profile`、`RA:report`、`RA:analysis-plan` 等流程内 skill 当作普通用户第一层入口推荐。
- 让 `RA:getting-started` 创建正式 job、执行取数、生成报告或自动注册 metadata。
- 运行 destructive git 命令或清理非本轮产生的用户改动。

---

## 必需模式

- 写 metadata 前先确认归属层：dataset、mapping、dictionary、source、audit、runtime registry、index、report 各归其位。
- 写入口文档前先确认三核归属：Metadata 管含义，Runtime Registry 管能不能取，Job 管本次实际用了什么；长期任务管理不属于 RealAnalyst job。
- 从 YAML 到 runtime registry 只能走 `metadata validate` -> `metadata index` -> `metadata sync-registry`。
- 正式分析、取数、metadata 维护前先复用 doctor 输出的 `python_command`、`skill_base_dir` 和 `registry_path`。
- Export 必须先解析 runtime source entry 和 spec，再校验字段和 filter。
- Report 只基于真实 metadata、connector 输出、export manifest、sample profile、mapping 或 dictionary evidence；没有可验证内容的 section 默认删除。
- CLI 面向 agent 时输出结构化 JSON，失败时包含可读错误和稳定 `error_code`。
- 读取 JSON manifest 中的路径时使用 `Path.resolve()` + `relative_to()` 防止 path escape。
- project-local 安装兼容 `.agents/skills`，不要硬编码源码仓根路径。

---

## 审查清单

审查 RealAnalyst 改动时，至少检查：

- 职责边界：改动是否把 metadata、runtime、report、analysis artifact 混在一起。
- 数据真源：是否把旧 report、sample 或 runtime enum 当业务定义真源。
- 输出契约：被 agent 调用的脚本 stdout 是否仍是可解析 JSON。
- 错误处理：失败是否明确、可复跑、不会静默跳过 required step。
- 安全性：SQL 是否参数化，路径是否限制在 workspace/job 目录。
- 安装兼容：源码仓路径和 `.agents/skills` 安装路径是否都能工作。
- 文档同步：`README.md`、`skills/README.md`、`SKILL.md`、adapter references 是否需要同步。
- 用户入口：README、skills README、llm-next-steps、getting-started 是否一致表达 3 个主入口、3 个补充入口和流程内 skill 弱化。
- Completion Summary：所有 `skills/*/SKILL.md` 是否都有统一结构，下一步建议是否按本次结果动态裁剪且不自动越权执行。
- 测试：是否有覆盖当前行为的 focused test 或 smoke command。

---

## 常见漏项

- 只跑 `metadata validate` 就宣称可取数；还需要 `metadata status` 或 registry/export smoke。
- 修报告时忘记处理 validate failed 的降级路径。
- 新增 script 但没有加到对应 `metadata.py` 或 skill 文档。
- 修改 report 输出格式却没有更新 `metadata-report/references/report-template.md`。
- 新增 skill 或改 skill 名称后漏掉 `skills/README.md`、根 README、installer 示例或 `skills-lock.json`。
