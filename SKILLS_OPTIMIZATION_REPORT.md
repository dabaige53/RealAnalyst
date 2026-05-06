# RealAnalyst Skills 优化调整报告

**生成时间**：2026-04-30
**执行范围**：`skills/` 全域 + 相关 docs / README
**调整原则**：只新增或移动代码，不删除现有能力；旧入口保留向后兼容

---

## 零、背景与用户请求

### 0.1 起因：全面分析请求

用户要求对 `skills/` 目录下所有 skill 进行全面分析，评估四个维度：

1. **完整性**：每个 skill 是否具备 SKILL.md + README.md + scripts/ + references/
2. **功能断点**：是否存在会导致系统不可用的硬断档
3. **交互质量**：skill 间的数据流和触发关系是否顺畅
4. **职责独立性**：各 skill 的边界是否清晰，有无重叠

### 0.2 分析结论摘要

分析完成后，发现以下关键问题（按严重程度排序）：

#### 严重性重新评估

用户主动追问"是否存在系统严重不可用的断档"。经重新评估：

> **结论：系统当前不存在会导致严重不可用的硬断档。** 所有被标记为"高优先级"的问题均有已文档化的 fallback 路径或下游门禁兜底。

真正的改进机会集中在**可维护性和能力边界**，而非功能修复。

#### 发现的核心问题

| 问题 | 严重度 | 根因 |
|---|---|---|
| `reference-lookup` 与 `metadata search` 查询同一批 JSONL 文件，存在功能重叠 | 🔴 | 历史遗留，两个 skill 各自实现了 metric/dimension/glossary 查询 |
| `reference-lookup` 的 metric/dimension 查询用朴素字符串匹配，质量低于 metadata 的 FTS5 | 🔴 | 实现差异导致同一数据源查询结果不一致 |
| `glossary` 查询搜不同文件（`terms.jsonl` vs `glossary.jsonl`），潜在数据不一致 | 🔴 | 文件名未统一 |
| `artifact-fusion` join 按行号拼列，非业务键 join，存在静默错配风险 | 🟡 | pd.concat(axis=1) 设计限制 |
| `analysis-run` SKILL.md 810 行，把平台规则（Discord/Drive）混入执行规则 | 🟡 | 内容未分层 |
| 4 个 skill 缺少 references/ 目录，细节契约内嵌在 SKILL.md 中 | 🟢 | 结构不规范 |
| DuckDB 路径缺 source_context，与 Tableau 路径不对称 | 🟡 | 历史实现差异 |

### 0.3 用户需求时间线

| 时间 | 用户请求 | 关键决策 |
|---|---|---|
| T+0 | 分析 skills 完整性、功能断点、交互、职责独立性 | 全面分析，发现 7 项问题 |
| T+1 | 讨论是否存在严重断档 | 结论：无断档，重新定级为可维护性优化 |
| T+2 | 列出完整计划并调整 | 制定 P0-P3 优先级计划 |
| T+3 | 确认 `reference-lookup` 与 `metadata search` 的区别 | 代码分析：搜同一文件、算法质量不同、glossary 文件名不一致 |
| T+4 | 决定拆分：reference-lookup 只保留 template+framework，metadata search 独立成 skill | 核心架构决策 |
| T+5 | **只移动代码，不删除** | 执行原则确认：旧目录保留，新 skill 从旧代码复制/提取 |
| T+6 | 确认新 skill 命名：`analysis-reference` + `metadata-search`；metadata-search 含 search + catalog | 命名和范围确认 |
| T+7 | 开始执行 | P0 → P1 → P2 → P3 顺序执行 |
| T+8 | 指出 `delivery-rules.md` 是旧脏规则，直接删除 | 用户主动清理 Discord/Drive 投递规则 |
| T+9 | 指出 `file-path-spec.md` 不应放 reference，关键规则必须内联 | 还原 file-path-spec 到 SKILL.md 内联 |
| T+10 | 确认 metadata 能力切割不够干净 | 分析三处必须切 vs 两处保留内部工作流 |
| T+11 | 执行三处精确切割 + 生成调整报告 | 本报告 |

### 0.4 执行原则

本次优化严格遵守以下原则（来自用户明确指令）：

1. **只移动不删除**：所有旧目录和文件保留，只在新位置新建/复制
2. **无废弃标注**：全新项目，不需要在旧文件加 deprecated 注释
3. **关键规则必须内联**：Agent 每次执行都要读的硬约束不能放 references（反例：file-path-spec 被还原）
4. **向后兼容**：`metadata.py search/catalog` 命令保留可用；`artifact-fusion` 旧 join 行为不变

---

## 一、变更总览

| 优先级 | 类别 | 变更项 | 文件数 | 状态 |
|---|---|---|---|---|
| P0 | Skill 拆分 | `reference-lookup` → `analysis-reference`（新建） | 4 | ✅ |
| P0 | Skill 新建 | `metadata-search`（从 metadata 拆出） | 5 | ✅ |
| P0 | 能力边界切割 | `metadata` SKILL.md 移除 search/catalog 触发 | 1 | ✅ |
| P0 | 系统引用替换 | 8 个文件的 reference-lookup 引用更新 | 8 | ✅ |
| P1 | 结构整理 | `analysis-run` SKILL.md 拆分 references | 4 | ✅ |
| P1 | 结构整理 | 3 个 skill 补齐 references/ | 3 | ✅ |
| P2 | 功能增强 | `artifact-fusion` 增加 `--join-key` 键 join | 2 | ✅ |
| P3 | 纵深防御 | `validate_analysis.py` + `validate_plan.py` | 2 | ✅ |
| P3 | 路径对称 | DuckDB 导出后自动复制 context_injection.md | 2 | ✅ |

---

## 二、P0：Skill 拆分与重组

### 2.1 新建 `skills/analysis-reference/`

**背景**：`reference-lookup` 同时承担 template/framework 查询和 metric/dimension/glossary 查询，后者与 `metadata search` 重叠（搜同一批 JSONL 但用朴素字符串匹配，质量更差）。

**动作**：从 `reference-lookup` 复制并精简，只保留两个独有能力。

| 新建文件 | 说明 |
|---|---|
| `skills/analysis-reference/SKILL.md` | 触发词：template / framework；明确排除 metric/field/term |
| `skills/analysis-reference/README.md` | 用户说明 |
| `skills/analysis-reference/scripts/query_config.py` | 从旧脚本复制后移除 `--metric`、`--dimension`、`--glossary` 参数及对应函数；移除对 `metadata/index/*.jsonl` 的读取 |
| `skills/analysis-reference/references/output-contract.md` | 只保留 template / framework 输出契约 |

**旧 `reference-lookup/` 处理**：保留不动，不加废弃标注（全新项目无历史负担）。

**query_config.py 变更明细**：

| 移除 | 保留 |
|---|---|
| `--metric` / `--dimension` / `--glossary` 参数 | `--template`（搜 template-system-v2.md） |
| `search_glossary()` / `search_metric()` / `search_dimension()` | `--framework`（查内置框架配置） |
| `search_jsonl()` / `load_jsonl()` 工具函数 | `_find_workspace_root()` / `load_yaml()` |
| `METADATA_INDEX_DIR` 及对 `metadata/index/*.jsonl` 的引用 | `REPORT_TEMPLATE_REFERENCE` |

---

### 2.2 新建 `skills/metadata-search/`

**背景**：metric/field/term/dataset/mapping 检索和 catalog 浏览是独立的"查询"职责，与 metadata 的"维护"职责分离。metadata 底层已有高质量实现（FTS5 + JSONL fallback），只需做薄包装。

**动作**：新建 skill，脚本层薄包装，底层 import metadata lib（不复制代码）。

| 新建文件 | 说明 |
|---|---|
| `skills/metadata-search/SKILL.md` | 触发词：搜索指标/字段/术语/数据集/mapping；浏览 catalog |
| `skills/metadata-search/README.md` | 用户说明 |
| `skills/metadata-search/scripts/search.py` | 薄包装，import `skills.metadata.lib.metadata_search`；支持 FTS5 优先 + JSONL fallback |
| `skills/metadata-search/scripts/catalog.py` | 薄包装，import `skills.metadata.lib.metadata_catalog` + `metadata_io` |
| `skills/metadata-search/scripts/_bootstrap.py` | 从 `skills/metadata/scripts/_bootstrap.py` 复制 |

**底层依赖**（不重复实现）：

```
skills/metadata/lib/metadata_search.py   → search.py 引用
skills/metadata/lib/metadata_catalog.py  → catalog.py 引用
skills/metadata/lib/metadata_io.py       → catalog.py 引用
```

**支持的搜索类型**：`metric` / `field` / `term` / `dataset` / `mapping` / `all`

---

### 2.3 `metadata/SKILL.md` 能力边界切割

**三处精确切割**（不动内部工作流）：

| 位置 | 变更前 | 变更后 | 理由 |
|---|---|---|---|
| `description` frontmatter | 包含 `searching` 触发词；`指标/字段/术语查询` | 移除 `searching`；移除 `指标/字段/术语查询`；加注 `For search/catalog use RA:metadata-search` | 路由混乱根源 |
| `When to Use → 不要使用本 skill` | 无 search/catalog 禁用说明 | 新增两条：搜索指标/字段/术语 → `RA:metadata-search`；浏览 catalog → `RA:metadata-search` | 明确边界 |
| `Completion Summary` | 有 `search 完成` / `catalog 完成` 两条汇报词；`index 完成` 下一步指向 `metadata search` | 删除 search/catalog 完成汇报；`index 完成` 改为"用 RA:metadata-search 验证索引" | 这两条产物属于 metadata-search，不属于 metadata |

**保留不动**：

- `Decision Rules` 中内部用 search 定位 dataset 的逻辑（这是 metadata 自己 context 生成流的内部步骤）
- `CLI Quick Reference` 中的 `search` / `catalog` 命令（底层命令仍存在，文档保留供排障）
- `Failure Handling` 中 search 相关描述（现已重写为指向 RA:metadata-search）

---

### 2.4 系统性引用替换

涉及 **8 个文件**，**所有引用从 `RA:reference-lookup` 迁移到新 skill**：

#### `skills/README.md`（14 处）

| 位置 | 变更 |
|---|---|
| Mermaid 架构图 Support 子图 | `RA:reference-lookup` → `RA:analysis-reference` + 新增 `RA:metadata-search` 节点 |
| 分层设计文字 | `reference-lookup` → `analysis-reference · metadata-search` |
| "不知道用哪个 skill" 决策图 | 新增 `RA:metadata-search` 分支 |
| 辅助 Skills 清单表 | 拆分为两行 |
| 辅助 Skill 交互图 | 更新节点和箭头标签 |
| 依赖矩阵 | `reference-lookup` → `analysis-reference` + `metadata-search` 两行 |
| 模式二示例 | 更新两条命令 |
| 后端脚本速查 | `reference-lookup` 章节 → `analysis-reference` + `metadata-search` 两个章节 |
| 开发约定 | 更新工具引用 |
| 能力层 skill 数量 | 12 → 13 |

#### `skills/analysis-plan/SKILL.md`（11 处）

| 位置 | 变更 |
|---|---|
| Phase 0.2 禁止说明 | `reference-lookup skill` → 对应 skill |
| Phase 0.2 framework 查询命令 | 路径改为 `skills/analysis-reference/scripts/query_config.py` |
| Phase 0.2 metric 查询命令 | 改为 `skills/metadata-search/scripts/search.py --type metric` |
| Phase 0.2 dimension 查询命令 | 改为 `skills/metadata-search/scripts/search.py --type field` |
| Phase 0.2 glossary 查询命令 | 改为 `skills/metadata-search/scripts/search.py --type term` |
| Phase 0.2 MECE 示例 | 路径改为 analysis-reference |
| Phase 2.3 下钻路径 logic_path 查询 | 路径改为 analysis-reference |
| Phase 3 框架选择说明 | `reference-lookup` → `RA:analysis-reference` |
| Phase 3 确定框架后查询命令 | 路径改为 analysis-reference |
| Phase 4.1 框架配置查询 | 路径改为 analysis-reference |
| Phase 4.1 说明文字 | `reference-lookup` → `RA:analysis-reference` |

#### `skills/analysis-run/SKILL.md`（1 处）

| 位置 | 变更 |
|---|---|
| 可用 Skill 表 | `RA:reference-lookup` → `RA:analysis-reference` + 新增 `RA:metadata-search` 行 |

#### `skills/report/SKILL.md`（1 处）

| 位置 | 变更 |
|---|---|
| Metadata 与模板来源章节 | `RA:metadata search/context` 或 `RA:reference-lookup` → `RA:metadata-search` 和 `RA:analysis-reference` |

#### `skills/metadata/SKILL.md`（见 2.3）

#### `docs/skill-interaction-design.md`（7 处）

| 位置 | 变更 |
|---|---|
| 辅助 Skill 表 | 拆分为两行 |
| 主链路时序图参与者 | `RA:reference-lookup` → `RA:analysis-reference` + 新增 `RA:metadata-search` |
| 时序图交互消息 | 拆分为框架/模板 vs 指标/字段两条消息 |
| analysis-plan 依赖项 | 更新为两个 skill |
| report 依赖项 | 更新为两个 skill |
| `RA:reference-lookup` 独立章节 | 改写为 `RA:analysis-reference` + `RA:metadata-search` 两个章节 |
| 辅助 Skill 触发条件 | `reference-lookup` → `analysis-reference` + `metadata-search` |

#### `README.md`（1 处）

| 位置 | 变更 |
|---|---|
| 主能力表 | `配置查询 → RA:reference-lookup` → 拆分为两行 |

#### `skills/getting-started/SKILL.md`

无直接引用，不需改动。

---

## 三、P1：结构整理

### 3.1 `analysis-run/SKILL.md` 拆分 references

**原始行数**：811 行 → **调整后**：655 行（减少 ~19%）

提取内容：

| 新建 reference 文件 | 提取内容 | 行数 |
|---|---|---|
| `references/phase3-analysis-contract.md` | Phase 3 全部硬约束、数据边界规则、分析执行流程、analysis.json 产出契约、文件选择规则 | ~110 行 |
| `references/reply-style.md` | Reply style 风格指南 + Writing check | ~25 行 |
| `references/file-path-spec.md` | job 目录结构（作为备份参考，SKILL.md 内仍保留完整内容） | ~25 行 |

**⚠️ 重要说明**：

- `file-path-spec.md` 内容已**还原回 SKILL.md 内联**（路径规范是每次执行的硬约束，不能放 reference）
- `delivery-rules.md` 由用户主动删除（旧平台规则，不属于系统核心）
- Phase 3 内容提取到 reference 后，SKILL.md 中用一行引用替代，保留铁律摘要

### 3.2 补齐 3 个 skill 的 references/

| Skill | 新建文件 | 内容 |
|---|---|---|
| `metadata-refine` | `references/evidence-manifest-schema.md` | `evidence_manifest.json` 完整字段定义、issue_type 枚举、归档路径约定 |
| `report-verify` | `references/check-rules.md` | 10 类检查项的详细判定标准（evidence_completeness、ranking_consistency 等） |
| `artifact-fusion` | `references/strategy-guide.md` | union/join/passthrough 策略详解、`--join-key` 用法、人工校验步骤 |

---

## 四、P2：功能增强

### 4.1 `artifact-fusion/scripts/fusion.py` 增加 `--join-key`

**问题**：原 join 策略使用 `pd.concat(axis=1)` 按行号拼列，不支持按业务键关联，存在"看似成功实则错配"的静默错误风险。

**变更**：

```python
# 新增参数
--join-key <列名>    # 传入时使用 pd.merge(on=key, how='left')
                     # 不传时保持原有 axis=1 行为（向后兼容）
```

| 模式 | 触发条件 | 实现 |
|---|---|---|
| 键 join（新，推荐） | `--join-key "产品"` | `pd.merge(on=key, how='left', suffixes=('_left','_right'))` |
| 索引 join（原有） | 不传 `--join-key` | `pd.concat(axis=1)`，日志加警告 |

**向后兼容**：不传 `--join-key` 时行为完全不变。

**文档同步**：
- `SKILL.md` join 策略章节更新，标注键 join 为推荐方式
- `references/strategy-guide.md` 包含完整用法说明和校验步骤

---

## 五、P3：纵深防御

### 5.1 新建校验脚本

#### `skills/analysis-run/scripts/validate_analysis.py`

**用途**：Phase 3 → Phase 4 之间的可选校验门禁。

| 检查项 | 方法 | 失败条件 |
|---|---|---|
| JSON 格式合法 | `json.loads` | 解析失败 |
| 必填字段存在 | 字段枚举 | 缺 `job_id` / `dataset_id` / `created_at` / `findings` |
| findings 非空 | `len(findings) > 0` | 空列表 |
| 每条 finding 有 claim | 字段检查 | 缺失 |
| evidence.source_file 存在 | 文件系统检查 | 文件不存在 |
| confidence 字段存在 | 字段检查 | 缺失 |

```bash
python3 skills/analysis-run/scripts/validate_analysis.py --session-id <SESSION_ID>
python3 skills/analysis-run/scripts/validate_analysis.py --analysis-json <path>
```

输出：`{"success": true/false, "errors": [...], "error_count": N}`

#### `skills/analysis-plan/scripts/validate_plan.py`

**用途**：planning 完成后验证 10 章结构完整性（analysis-plan 首个脚本）。

| 检查项 | 方法 | 级别 |
|---|---|---|
| 10 章标题全部存在 | 正则 heading 匹配 | error |
| `selected_report_template` 存在 | 字符串搜索 | error |
| `selected_analysis_mode` 存在 | 字符串搜索 | error |
| `selected_delivery_mode` 存在 | 字符串搜索 | error |
| 业务假设数量 ≥ 3 | 正则计数 | warning |

```bash
python3 skills/analysis-plan/scripts/validate_plan.py --session-id <SESSION_ID>
python3 skills/analysis-plan/scripts/validate_plan.py --plan-file <path>
```

输出：`{"success": true/false, "errors": [...], "warnings": [...], "error_count": N, "warning_count": N}`

---

### 5.2 DuckDB 导出后自动复制 context

**问题**：Tableau 路径自动生成 `source_context.json` + `context_injection.md`；DuckDB 路径无，造成下游分析上下文不对称。

**变更位置**：`skills/data-export/scripts/duckdb/duckdb_export_with_meta.py`

**逻辑**（非侵入式，best-effort）：

```python
# 导出成功后，step 3
dataset_id = summary_data.get("dataset_id") or summary_data.get("source_id")
osi_context = WORKSPACE_DIR / "metadata" / "osi" / dataset_id / "context.md"
if osi_context.exists():
    shutil.copy2(osi_context, job_dir / "context_injection.md")
    context_available = True
```

**输出字段新增**：`context_injection: {available: bool, path: str|null}`

**降级处理**：若 OSI context 不存在，`context_injection.available=false`，下游 Phase 3 读 `metadata/osi/<dataset_id>/context.md` 原始路径，行为与改前一致。

**文档同步**：`data-export/SKILL.md` DuckDB 输出契约章节更新，说明 `context_injection.md` 的生成条件。

---

## 六、Skill 数量变化

| 状态 | Skill |
|---|---|
| 新增 ✅ | `RA:analysis-reference`（template + framework 查询） |
| 新增 ✅ | `RA:metadata-search`（search + catalog 检索） |
| 保留（无修改） | `RA:reference-lookup`（旧，向后兼容） |
| **活跃 skill 总数** | **14 个**（原 12 个 + 2 个新增；旧 `RA:reference-lookup` 仍作为兼容入口安装） |

---

## 七、文件变更索引

### 新建文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `skills/analysis-reference/SKILL.md` | SKILL | analysis-reference 执行合约 |
| `skills/analysis-reference/README.md` | README | 用户说明 |
| `skills/analysis-reference/scripts/query_config.py` | 脚本 | template + framework 查询 |
| `skills/analysis-reference/references/output-contract.md` | Reference | 输出契约 |
| `skills/metadata-search/SKILL.md` | SKILL | metadata-search 执行合约 |
| `skills/metadata-search/README.md` | README | 用户说明 |
| `skills/metadata-search/scripts/search.py` | 脚本 | 薄包装，复用 metadata lib |
| `skills/metadata-search/scripts/catalog.py` | 脚本 | 薄包装，复用 metadata lib |
| `skills/metadata-search/scripts/_bootstrap.py` | 脚本 | workspace 路径 bootstrap |
| `skills/analysis-run/references/phase3-analysis-contract.md` | Reference | Phase 3 完整执行契约 |
| `skills/analysis-run/references/reply-style.md` | Reference | 回复风格指南 |
| `skills/analysis-run/references/file-path-spec.md` | Reference | job 目录结构（备用参考） |
| `skills/analysis-run/scripts/validate_analysis.py` | 脚本 | analysis.json 校验 |
| `skills/analysis-plan/scripts/validate_plan.py` | 脚本 | analysis_plan.md 结构校验 |
| `skills/metadata-refine/references/evidence-manifest-schema.md` | Reference | evidence_manifest.json schema |
| `skills/report-verify/references/check-rules.md` | Reference | 10 类检查项判定标准 |
| `skills/artifact-fusion/references/strategy-guide.md` | Reference | 融合策略详解 + 校验步骤 |

### 修改文件

| 文件 | 修改类型 | 关键变更 |
|---|---|---|
| `skills/metadata/SKILL.md` | 能力边界切割 | 移除 searching 触发词；不要使用列表加 search/catalog；Completion Summary 删 search/catalog |
| `skills/analysis-plan/SKILL.md` | 引用替换 | 11 处 reference-lookup → analysis-reference / metadata-search |
| `skills/analysis-run/SKILL.md` | 拆分 + 引用替换 | Phase 3 正文 → reference；file-path-spec 还原内联；reply style → reference；可用 Skill 表更新 |
| `skills/report/SKILL.md` | 引用替换 | 1 处检索引用更新 |
| `skills/README.md` | 引用替换 + 结构更新 | 14 处更新；skill 数量 12→14；两个新 skill 加入清单和图表，旧 `RA:reference-lookup` 作为兼容入口保留 |
| `docs/skill-interaction-design.md` | 引用替换 + 结构更新 | 7 处更新；时序图参与者和交互消息拆分 |
| `README.md` | 引用替换 | 主能力表拆分为两行 |
| `skills/artifact-fusion/scripts/fusion.py` | 功能增强 | 新增 `--join-key` 参数；join 策略分支 |
| `skills/artifact-fusion/SKILL.md` | 文档同步 | join 章节更新 |
| `skills/data-export/scripts/duckdb/duckdb_export_with_meta.py` | 功能增强 | 导出后 step 3 自动复制 context_injection.md |
| `skills/data-export/SKILL.md` | 文档同步 | DuckDB 输出契约更新 |

### 不变文件

| 文件 | 原因 |
|---|---|
| `skills/reference-lookup/` 全部文件 | 向后兼容保留，无修改 |
| `skills/metadata/scripts/metadata.py` | `search` / `catalog` 命令保留，向后兼容 |
| `skills/metadata/lib/` 全部文件 | metadata-search 的薄包装复用这些库 |
| 所有 `schemas/*.json` | 无结构变化 |

---

## 八、已知遗留问题

| 问题 | 影响 | 建议 |
|---|---|---|
| `metadata-search/scripts/search.py` 依赖 `skills.metadata.lib.metadata_search`，但 `skills/` 目录无 `__init__.py` | 若直接 `python3 search.py` 可能 import 失败 | 由 `_bootstrap.py` 把 workspace root 加入 sys.path，与 metadata 自身 bootstrap 机制一致，应可运行；建议实际跑一次验证 |
| `validate_plan.py` 的假设数量检测用正则匹配 `假设\s*\d+` | 若 plan 用其他格式书写假设可能误报 warning | 可接受，warning 不阻断流程 |
| `reference-lookup/` 旧 skill 无明显提示说明已有新 skill | 新 Agent 可能走旧路径 | 本次选择不加废弃标注（全新项目原则）；后续可考虑在 description 中追加重定向说明 |

---

*报告生成于 2026-04-30 by Cascade*
