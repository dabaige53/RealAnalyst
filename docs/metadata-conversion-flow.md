# Metadata Conversion Flow

本文定义收敛后的元数据转换流程。当前阶段的重点是统一 metadata 入口、明确 connector adapter 边界、保留 YAML 作为 LLM 维护真源。

## 转换层次

1. 原始证据：`metadata/sources/*`
2. YAML 真源：`metadata/dictionaries/*.yaml`、`metadata/mappings/*.yaml`、`metadata/datasets/*.yaml`
3. 轻量索引：`metadata/index/*.jsonl` + `metadata/index/search.db`（FTS5）
4. 数据集目录：`metadata catalog` 输出 JSON
5. 上下文包：`metadata context` 输出 JSON（支持多数据集）
6. connector adapter：Tableau/DuckDB 元数据发现素材
7. 运行态 registry：`runtime/registry.db`（含 source_groups 表）
8. 一致性比对：`metadata reconcile` 比对 runtime vs metadata 差异
9. 标准交换：`metadata/osi/*.osi.yaml`

## 当前阶段边界

不手工从 YAML 覆盖 registry.db；通过 `metadata sync-registry` 把已校验 dataset YAML 受控 upsert 到运行层。

Tableau/DuckDB 是 connector adapter，不是用户优先选择的独立元数据 skill。

OSI 是交换层，不进入本地分析主路径。

## 推荐转换顺序

```text
metadata validate
→ metadata index（JSONL + search.db）
→ metadata sync-registry
→ metadata status
→ metadata catalog（浏览全部数据集）
→ metadata search（FTS5 BM25）
→ metadata context（单数据集或多数据集）
→ metadata reconcile（可选，查运行时 vs 元数据一致性）
→ analysis-run 读取 context pack
→ query_registry 读取运行层 source 信息
→ data-profile / report / report-verify 标记推断口径
→ metadata export-osi（仅交换场景）
```
