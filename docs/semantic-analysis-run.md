# Semantic Analysis Workflow

这份说明描述从元数据维护到语义分析执行的端到端路径，帮助产品和分析协作时明确每一层的职责边界。

## 分层定位

- YAML 是 LLM 维护真源：`dictionaries` 保存公共语义，`mappings` 保存字段映射，`datasets` 保存真实数据源 metadata。
- sources 是证据层：保存原始材料、迁移输入和 connector 发现素材。
- index 是检索层：由 `metadata index` 生成 JSONL + FTS5 `search.db`，面向快速召回字段、指标、mapping、术语和数据集线索。
- catalog 是目录层：由 `metadata catalog` 生成所有数据集的轻量摘要，帮助发现和选择数据源。
- context pack 是对话层：由 `metadata context` 生成，只携带本轮分析需要的最小上下文。支持多数据集合并 context。
- registry.db 是运行层：服务执行稳定性，通过 `metadata sync-registry` 从已校验 dataset YAML 受控同步。含 `source_groups` 表管理多源分组。
- reconcile 是一致性层：由 `metadata reconcile` 比对 runtime_config.db 与 metadata YAML，发现语义漂移。
- connector adapter 是初始化素材层：Tableau/DuckDB 只负责发现外部系统字段、筛选器、catalog 和运行所需 source 信息。
- OSI 是交换层：用于跨系统交换语义模型，不进入本地分析主路径。

## 端到端顺序

1. `metadata validate` 校验 YAML 契约，先确认维护真源可用。
2. `metadata index` 从 YAML 生成 JSONL + FTS5 `search.db`。
3. `metadata catalog` 浏览全部可用数据集，缩小选择范围。
4. `metadata search` 在需求理解阶段召回候选数据集、字段和指标（FTS5 BM25 排序）。
5. `metadata context` 把候选结果压缩成 context pack，交给对话和规划使用。支持多数据集。
6. 需要取数前运行 `metadata status`，确认 runtime registry 和 export-ready 状态。
7. `RA:analysis-run` 在执行阶段通过 `query_registry` 读取运行层信息，`--source` 输出会附带 `associated_groups`。
8. 报告生成后进入 `RA:report-verify`，重点检查推断口径、review 标记和结果可复核性。
9. 可选：`metadata reconcile` 比对运行时与元数据一致性。
10. 需要跨系统交换时，走 OSI export；这是交换路径，不是分析主路径。

## 边界

- 需求理解阶段不直接读取完整 YAML，先通过 `metadata search` 和 `metadata context` 控制上下文范围。
- connector adapter 不替代 YAML；它只提供初始化素材。
- OSI 不替代 `metadata search` 或 `metadata context`；它服务交换，不服务本地需求召回。
- `registry.db` 是运行时锁定的 source layer，面向执行稳定性，不承担人工维护职责。
- 不手工从 YAML 覆盖 registry.db；运行层同步必须走 `metadata sync-registry`。
