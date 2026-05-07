---
name: "RA:metadata-search"
description: |
  Use when: (1) Need to search for metric, field, term, dataset, or mapping definitions from the metadata index,
  (2) Need to browse available datasets before starting analysis, (3) Need a lightweight lookup result
  instead of reading full YAML files.
  Triggers: 搜索指标, 搜索字段, 搜索术语, 搜索数据集, metadata search, 浏览数据集目录, catalog, dataset discovery.
---

# Metadata Search Skill

按需搜索 metadata index 中的指标、字段、术语、数据集和映射定义；浏览可用数据集目录。

核心原则：**低 token 开销的语义检索入口，不读完整 YAML，不维护元数据。**

本 skill 是辅助入口，不放普通用户第一层。只有用户明确想查字段/指标/术语/dataset 是否已维护，或其它 skill 需要轻量检索结果时使用。

## When to Use

使用本 skill：

- 需要搜指标、字段、术语、dataset 或 mapping 定义。
- 分析前需要浏览可用数据集全貌（catalog）。
- 需要 machine-readable JSON 结果供 Agent 或脚本消费。

不要使用本 skill：

- 维护 YAML、注册数据集、生成 index/context：使用 `RA:metadata`。
- 查报告模板或分析框架：使用 `RA:analysis-reference`。
- 执行正式分析或取数：普通用户进入 `RA:analysis-run`；仅在高级手工编排或排障时由流程调用 `RA:data-export`。

## 核心流程

### 搜索（search）

```bash
python3 {baseDir}/skills/metadata-search/scripts/search.py --type metric --query 收入
python3 {baseDir}/skills/metadata-search/scripts/search.py --type field --query 航班日期
python3 {baseDir}/skills/metadata-search/scripts/search.py --type term --query 转化率
python3 {baseDir}/skills/metadata-search/scripts/search.py --type dataset --query 销售
python3 {baseDir}/skills/metadata-search/scripts/search.py --type mapping --query 渠道
python3 {baseDir}/skills/metadata-search/scripts/search.py --type all --query 订单量
```

支持 6 类搜索类型：`metric` / `field` / `term` / `dataset` / `mapping` / `all`

优先使用 FTS5 全文检索后端（`metadata/index/search.db`），fallback 到 JSONL 朴素搜索。

### 浏览数据集目录（catalog）

```bash
python3 {baseDir}/skills/metadata-search/scripts/catalog.py
python3 {baseDir}/skills/metadata-search/scripts/catalog.py --domain <domain>
python3 {baseDir}/skills/metadata-search/scripts/catalog.py --group-by domain
```

catalog 输出每个 dataset 的轻量摘要（id / display_name / domain / grain / top 3 metrics / suitable_for / field_count / metric_count / review_required）。

## 输出契约

### search 输出

```json
{
  "success": true,
  "query": "收入",
  "type": "metric",
  "backend": "fts5",
  "matches": [
    { "id": "revenue", "name": "收入", "definition": "..." }
  ]
}
```

- `backend`：`fts5`（优先）或 `jsonl`（fallback）
- `success=false` 时包含 `message` 和 `missing` 字段，提示需要先运行 `metadata index`

### catalog 输出

JSON 对象，key 为 dataset_id，value 为摘要字段。

## 前置条件

- metadata index 必须已生成：`python3 {baseDir}/skills/metadata/scripts/metadata.py index`
- 若 index 缺失，search 返回 `success=false` 并给出修复命令

## 验证

```bash
python3 {baseDir}/skills/metadata-search/scripts/search.py --type all --query test
python3 {baseDir}/skills/metadata-search/scripts/catalog.py
```

## Completion Summary

查询完成后，用下面结构向用户汇报，并按本次结果动态裁剪：

```text
完成情况：
- 已搜索类型：<metric / field / term / dataset / mapping / all / catalog>
- 命中数量：<count>
- 使用后端：<fts5 / jsonl>

下一步建议：
- 最推荐下一步：/skill RA:metadata ...（需要生成 context、维护 YAML 或补注册时）
- 可选下一步：/skill RA:analysis-run ...（命中 dataset 已可分析且用户要正式分析）
- 可选下一步：/skill RA:metadata-report ...（用户只想查看数据集长期口径说明）

边界提醒：
- 本 skill 只检索生成层 index / catalog，没有维护 YAML、同步 registry 或执行分析。
- 搜索命中不是业务定义真源；正式定义仍以 Metadata Core 的 YAML / dictionary / mapping / audit 为准。
```
