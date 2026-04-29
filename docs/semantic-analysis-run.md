# Semantic Analysis Workflow

这份说明描述从元数据维护到语义分析执行的端到端路径，帮助产品和分析协作时明确每一层的职责边界。

## 分层定位

- YAML 是 LLM 维护真源：`dictionaries` 保存公共语义，`mappings` 保存字段映射，`datasets` 保存真实数据源 metadata。
- sources 是证据层：保存原始材料、迁移输入和 connector 发现素材。
- index 是检索层：由 `metadata index` 生成，面向快速召回字段、指标、mapping、术语和数据集线索。
- context pack 是对话层：由 `metadata context` 生成，只携带本轮分析需要的最小上下文。
- registry.db 是运行层：服务执行稳定性，不从 YAML 反写 registry.db。
- connector adapter 是初始化素材层：Tableau/DuckDB 只负责发现外部系统字段、筛选器、catalog 和运行所需 source 信息。
- OSI 是交换层：用于跨系统交换语义模型，不进入本地分析主路径。

## 端到端顺序

1. `metadata validate` 校验 YAML 契约，先确认维护真源可用。
2. `metadata index` 从 YAML 生成轻量 index。
3. `metadata search` 在需求理解阶段召回候选数据集、字段和指标。
4. `metadata context` 把候选结果压缩成 context pack，交给对话和规划使用。
5. `RA:analysis-run` 在执行阶段通过 `query_registry` 读取运行层信息。
6. 报告生成后进入 `RA:report-verify`，重点检查推断口径、review 标记和结果可复核性。
7. 需要跨系统交换时，走 OSI export；这是交换路径，不是分析主路径。

## 边界

- 需求理解阶段不直接读取完整 YAML，先通过 `metadata search` 和 `metadata context` 控制上下文范围。
- connector adapter 不替代 YAML；它只提供初始化素材。
- OSI 不替代 `metadata search` 或 `metadata context`；它服务交换，不服务本地需求召回。
- `registry.db` 是运行时锁定的 source layer，面向执行稳定性，不承担人工维护职责。
- 当前阶段不从 YAML 反写 registry.db。
