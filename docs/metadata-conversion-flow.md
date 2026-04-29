# Metadata Conversion Flow

本文定义收敛后的元数据转换流程。当前阶段的重点是统一 metadata 入口、明确 connector adapter 边界、保留 YAML 作为 LLM 维护真源。

## 转换层次

1. 原始证据：`metadata/sources/*`
2. YAML 真源：`metadata/dictionaries/*.yaml`、`metadata/mappings/*.yaml`、`metadata/datasets/*.yaml`
3. 轻量索引：`metadata/index/*.jsonl`
4. 上下文包：`metadata context` 输出 JSON
5. connector adapter：Tableau/DuckDB 元数据发现素材
6. 运行态 registry：`runtime/tableau/registry.db`
7. 标准交换：`metadata/osi/*.osi.yaml`

## 当前阶段边界

当前阶段不从 YAML 反写 registry.db。

Tableau/DuckDB 是 connector adapter，不是用户优先选择的独立元数据 skill。

OSI 是交换层，不进入本地分析主路径。

## 推荐转换顺序

```text
metadata validate
→ metadata index
→ metadata search
→ metadata context
→ analysis-run 读取 context pack
→ query_registry 读取运行层 source 信息
→ data-profile / report / report-verify 标记推断口径
→ metadata export-osi（仅交换场景）
```
