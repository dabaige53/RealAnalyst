# Semantic Analysis Workflow

这份说明描述从 metadata 注册到正式分析交付的端到端路径，帮助产品和分析协作时明确 Metadata Core、Runtime Registry Core、Job Core 的职责边界。

## 分层定位

- Metadata Core 管“含义”：`dictionaries` 保存公共语义，`mappings` 保存字段映射，`datasets` 保存真实数据源 metadata，`sources` 保存证据，`audit` 保存关系和维护记录。
- Runtime Registry Core 管“能不能取”：`runtime/registry.db` 通过 `metadata sync-registry` 从已校验 dataset YAML 受控同步，保存 source、字段、filter、parameter 和 `source_groups`。
- Job Core 管“这次实际用了什么”：`jobs/{SESSION_ID}/` 保存 plan、export、profile、analysis、report、verification、feedback 和 artifact index。
- index 是生成检索层：由 `metadata index` 生成 JSONL + FTS5 `search.db`，面向快速召回字段、指标、mapping、术语和数据集线索。
- catalog 是目录层：由 `metadata catalog` 生成所有数据集的轻量摘要，帮助发现和选择数据源。
- context pack 是对话层：由 `metadata context` 生成，只携带本轮分析需要的最小上下文。支持多数据集合并 context。
- reconcile 是一致性层：由 `metadata reconcile` 比对 `runtime/registry.db` 与 metadata YAML，发现语义漂移。
- connector adapter 是初始化素材层：Tableau/DuckDB/CSV 只负责发现外部系统字段、筛选器、catalog 和运行所需 source 信息。
- OSI 是交换层：用于跨系统交换语义模型，不进入本地分析主路径。

LLM 不是真实事实源。LLM 可以起草定义、组织证据、生成计划、写报告、发现口径缺口和整理 refine 材料，但不能把推断定义直接标成事实，不能隐式写回正式 metadata，不能用聊天记忆替代 job artifacts。

## 端到端顺序

1. 不确定从哪里开始时，先用 `RA:getting-started` 做 minimal status check 和 skill routing。
2. 如果数据源未注册，进入 `RA:metadata` 做最小可分析注册：dataset id、source 类型、可用取数方式、核心时间/主体/维度/指标候选、定义状态、本次字段可找到。
3. `metadata validate` 校验 YAML 契约，先确认维护真源可用。
4. `metadata index` 从 YAML 生成 JSONL + FTS5 `search.db`。
5. `metadata sync-registry --dataset-id ...` 把已校验 dataset 同步到 Runtime Registry Core。
6. `metadata status --dataset-id ...` 确认 metadata_yaml、metadata_index、runtime_registry 和 export_ready。
7. 需要长期口径说明时，用户主动调用 `RA:metadata-report`；最小注册完成后只提示，不自动生成。
8. 数据已准备好后，进入 `RA:analysis-run` 做正式完整分析。它不吞掉 metadata 注册流程。
9. `RA:analysis-run` 内部编排 `RA:analysis-plan`、`RA:data-export`、`RA:data-profile`、LLM 分析、`RA:report`、`RA:report-verify`。
10. 报告生成后进入 `RA:report-verify`，重点检查推断口径、review 标记和结果可复核性。
11. 分析中如发现字段定义不清、指标口径待修或证据不足，只记录到 job feedback，不修改正式 YAML。
12. 用户主动调用 `RA:metadata-refine`，把 job feedback、profile、CSV 探查和用户反馈整理为 `metadata/sources/refine/` 参考材料。
13. 用户主动回到 `RA:metadata` 基于 refine pack 修正正式 YAML，并运行 validate / index / sync-registry。
14. 可选：`metadata reconcile` 比对运行时与元数据一致性。
15. 需要跨系统交换时，走 OSI export；这是交换路径，不是分析主路径。

## 边界

- 需求理解阶段不直接读取完整 YAML，先通过 `metadata search` 和 `metadata context` 控制上下文范围。
- connector adapter 不替代 YAML；它只提供初始化素材。
- OSI 不替代 `metadata search` 或 `metadata context`；它服务交换，不服务本地需求召回。
- `registry.db` 是运行时锁定的 source layer，面向执行稳定性，不承担人工维护职责。
- 不手工从 YAML 覆盖 registry.db；运行层同步必须走 `metadata sync-registry`。
- dataset YAML 是轻量语义入口，不保存 profile、sample values、enum values、registry snapshot、report 结论或证据全文。
- `RA:analysis-run` 是正式分析入口，不负责自动注册正式 metadata；未注册时先交给 `RA:metadata`。
- 分析后维护遵循“分析不中断，维护不断流，正式写回有边界”：feedback 先进 job / refine pack，正式 YAML 写回必须由用户主动触发。
- RealAnalyst job 不承担长期项目管理；长期任务目标和阶段推进交给外部 continuity layer。
