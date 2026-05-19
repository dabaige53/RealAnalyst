# brainstorm: optimize metadata field identity contract

## Goal

优化 RealAnalyst 的 dataset YAML 字段身份模型，核心目标是**删除冗余名称字段**，把 dataset 字段身份收敛到最小必要集合。普通字段默认只保留三类名称：`name` 标准语义 ID、`display_name` 语义层中文名、`physical_name` 真实源字段名；`source_field`、`standard_id`、`aliases/synonyms` 不再作为 dataset 常规字段输出。系统仍要能判断 `name` 是真实引用了标准语义，还是 AI/LLM 临时推断。

## What I Already Know

* 当前生成的 dataset YAML 会出现明显重复，例如：

  ```yaml
  - name: segment
    physical_name: 航段
    display_name: 航段
    standard_id: route
    source_field: 航段
  ```

* 重复的根因不是值相同，而是 dataset 层维护了太多“名称类字段”，并且 `display_name` 的职责没有被定义成“语义层中文名”：
  * `name` 像标准语义 ID。
  * `standard_id` 也像标准语义 ID。
  * `physical_name` 和 `source_field` 都像源字段。
  * `display_name` 经常只是 `physical_name` 的复制，但它真正应该表示标准语义的中文名称。
  * `aliases/synonyms` 如果进入 dataset，又会把标准语义层的同义词复制一遍。
* 现有 contract 已经说明：
  * `fields[].name` 是 stable semantic identifier。
  * 中文展示名放 `display_name`。
  * 物理源字段放 `physical_name` 或 `source_field`。
* 但现有 contract 还不够细：
  * 没有说 dataset 里是否允许同时出现 `name` 和 `standard_id`。
  * 没有说 `source_field` 是常规字段还是 fallback/override。
  * 没有说 `display_name == physical_name` 时是否应该输出。
  * 没有强校验 `business_definition.ref` 是否真的能证明 `name` 是标准语义引用。
* 历史 memory 显示，之前已经有 field identity cleanup，把 `name = stable semantic ID`、`display_name = 中文展示`、`physical_name/source_field = 源字段` 作为基础 contract；本任务要进一步细化和落地。

## Current Problem

当前问题集中在一个核心方向：dataset YAML 名称字段过多。优化目标不是把每个名称字段解释得更复杂，而是将 dataset 字段面收敛成三类必要名称，并把其他名称关系交给 dictionary / mapping / ref。

### 0. Dataset 名称字段过多

普通字段现在可能同时出现：

```yaml
name: segment
physical_name: 航段
display_name: 航段
standard_id: route
source_field: 航段
synonyms: [航段]
```

这会让维护者无法判断哪个才是事实，哪个才是标准语义，哪个只是展示或别名。最终目标是收敛成：

```yaml
name: route_segment
display_name: 航段
physical_name: 航段
```

其中 `display_name` 不是任意展示覆盖，而是语义层中文名。必要的定义来源用现有 `business_definition.ref` 证明，不再额外增加名称字段。

### 1. `name` 和 `standard_id` 冲突

如果 dataset 字段已经写：

```yaml
name: route_segment
```

并且它表示当前字段绑定到标准语义 `route_segment`，那么再写：

```yaml
standard_id: route_segment
```

就是同层重复。

更合理的职责是：

```text
mapping.view_field -> mapping.standard_id
dataset.name = mapping.standard_id
```

也就是：

* `standard_id` 属于 `metadata/mappings/*.yaml`。
* dataset 使用 `name` 承接标准语义 ID。
* dataset 字段层不再常规输出 `standard_id`。

### 2. `source_field` 和 `physical_name` 冲突

普通字段里：

```yaml
physical_name: 航段
source_field: 航段
```

没有增加信息。

更合理的职责是：

* `physical_name`：当前接入数据源里的真实字段名，来自 DuckDB / Tableau / CSV / schema。
* `source_field`：遗留执行定位 / override 字段，不表达业务语义，也不表达别名；只有现有执行代码暂时无法通过 `physical_name`、mapping 或 expression 找到取数字段时才允许保留。

因此普通字段默认删除 `source_field`。如果现有执行代码还依赖它，本任务也应把后续迁移目标写清楚：先兼容读取，生成时不再新增。

### 3. `display_name` 和 `physical_name` 重复

如果源字段本来就是清晰中文业务名：

```yaml
physical_name: 航段
display_name: 航段
```

如果 `display_name` 只是 `physical_name` 的机械复制，信息量确实很低；但完全删除会影响中文语义展示、检索和用户问题理解。更合理的做法不是删除 `display_name`，而是把它定义为“语义层中文名”：它可以等于 `physical_name`，但含义不同。

更合理的职责是：

* `display_name` 是单一正式的语义层中文名，不是 alias。
* aliases / synonyms 是同一个语义的其他叫法，用于理解用户查询，应该优先放在 dictionary / glossary / metric definition。
* `display_name` 作为中文语义锚点必须保留；标准层已有中文名时，dataset 生成时应沿用标准层中文名。
* 如果 `display_name == physical_name`，不是冗余错误，而是“源字段名刚好就是标准中文名”。

### 4. `business_definition.ref` 没有被用严

目前字段里已有：

```yaml
business_definition:
  ref: mapping:duckdb.ho.dim_ho_flight_type.mapping:route
```

但还需要明确：

* 这个 `ref` 是否能证明 `name` 真实引用了 mapping / dictionary / glossary 中的标准语义。
* 如果 `ref` 找不到，`name` 不能被当作 linked 标准语义。
* 如果 `name` 是 AI/LLM 推断，应明确标记 `source_type: inferred` 或 `needs_review: true`。

## Reduced Field Surface Contract

本任务的产品方向是减少字段数量。dataset 字段层不再把所有名称都摊开维护，而是只保留最小绑定信息。

### 常规 dataset 字段允许的名称类字段

| Field | Keep? | Reason |
| --- | --- | --- |
| `name` | 保留 | 当前 dataset 绑定的标准语义 ID；必须能通过 `business_definition.ref` 或状态判断来源 |
| `display_name` | 保留 | 语义层中文名；用于报告展示、搜索召回和用户问题理解，不承担 alias 职责 |
| `physical_name` | 保留 | 当前接入数据源里的真实字段名，是数据源事实 |
| `business_definition.ref` | 保留 | 证明 `name` 的来源或定义，不新增 `semantic_ref` |

### 常规 dataset 字段删除的名称类字段

| Field | Default action | Replacement |
| --- | --- | --- |
| `standard_id` | 从 dataset 删除 | 放在 mapping；dataset 用 `name` 承接 |
| `source_field` | 从普通字段删除 | 执行优先用 `physical_name`；映射用 mapping；指标用 expression |
| `aliases` / `synonyms` | 从 dataset 常规字段删除 | 放在 dictionary / glossary / metric definition |

只有明确 override/legacy 场景才允许临时保留这些字段，并且需要 validator/report 标出原因。

### Dataset field item

普通字段的最小结构：

```yaml
fields:
  - name: route_segment
    display_name: 航段
    physical_name: 航段
    role: dimension
    type: category
    description: 航段字段。
    business_definition:
      text: 航班经营中的航段维度。
      source_type: mapping
      ref: mapping:duckdb.ho.dim_ho_flight_type.mapping:route_segment
      confidence: 0.8
      needs_review: false
```

字段职责：

| Field | Responsibility | Source | Rule |
| --- | --- | --- | --- |
| `name` | 当前 dataset 内绑定的标准语义 ID | dictionary / mapping / glossary；若无则 AI/maintainer inferred | 必填；必须能判断 linked 还是 inferred |
| `display_name` | 语义层中文名 | dictionary / glossary / metric definition；无标准层时由人工/LLM 推断并 review | 必填；用于中文展示和检索，不用于别名集合 |
| `physical_name` | 当前数据源真实字段名 | schema / connector / source profile | 字段层必填，除非字段不是直接源字段 |
| `aliases` / `synonyms` | 同一标准语义的其他叫法 | dictionary / glossary / metric definition | 默认删除，不进入普通 dataset 字段 |
| `source_field` | 遗留执行定位 / override 字段 | legacy executor / mapping miss / special view field | 默认删除；不是业务源、不是中文名、不是 alias |
| `standard_id` | 源字段映射到标准语义 ID | mapping | 必须从 dataset 字段层删除 |
| `business_definition.ref` | 证明 `name` 的定义或映射来源 | dictionary / mapping / audit | 应复用现有字段，不新增 `semantic_ref` |

### Dataset metric item

指标最小结构：

```yaml
metrics:
  - name: passenger_revenue
    display_name: 客运收入
    expression: SUM(票款收入)
    aggregation: sum
    unit: 元
    business_definition:
      text: 客运收入指标。
      source_type: dictionary
      ref: dictionary:juneyao.metrics:passenger_revenue
      confidence: 0.9
      needs_review: false
```

指标职责：

| Field | Responsibility | Rule |
| --- | --- | --- |
| `name` | 标准指标 ID | 必须引用 dictionary / metric definition，或标记 inferred/pending |
| `display_name` | 标准指标中文名 | 必填；来自 dictionary / metric definition，不能当 aliases 用 |
| `expression` | 当前 dataset 如何实现指标 | 优先使用标准字段 ID 组合；必要时用真实字段并可追溯 |
| `source_field` | 简单单字段指标的遗留执行 shortcut | 只有 executor 仍需要、无 mapping、或表达式难解析时输出；长期应由 expression / mapping 替代 |
| `physical_name` | 源表已经有同名指标列时可使用 | 例如源表已有 `客座率`，可以作为真实字段事实 |
| `business_definition.ref` | 指标定义来源 | 必须指向 dictionary / metric definition / audit |

### Mapping item

mapping 负责源字段到标准语义：

```yaml
mappings:
  - type: dimension
    view_field: 航段
    standard_id: route_segment
```

mapping 职责：

| Field | Responsibility |
| --- | --- |
| `view_field` | 接入表/视图/导出层看到的源字段名 |
| `standard_id` | 该源字段对应的标准语义 ID |
| `field_id_or_override` | 兼容旧字段或人工覆盖，不应复制到 dataset 字段层 |

## Optimization Rules

### Generator output rules

1. 普通字段默认输出：

   ```text
   name + display_name + physical_name + role + type + business_definition
   ```

   `description` 只有能写出具体业务说明时保留；不要为了撑结构重复 `business_definition.text`。

2. `standard_id` 不输出到 dataset 字段层。

3. `source_field` 默认从普通字段删除；只有以下情况允许临时输出：
   * legacy executor 仍硬依赖 `source_field`，且本任务尚未迁移到 source resolution。
   * 当前 dataset 需要显式覆盖 mapping 或 `physical_name` 的执行字段。
   * 无 mapping、无可解析 expression，且该 dataset 必须临时独立执行。

4. `display_name` 默认保留，但只表示语义层中文名：
   * 优先来自 dictionary / glossary / metric definition 的正式中文名。
   * 如果源字段本身就是清晰中文业务名，可以等于 `physical_name`。
   * 如果只是同义词、俗称、用户可能说法，不写入 dataset `display_name`，应维护到 dictionary / glossary 的 `aliases` / `synonyms`。
   * 不允许把 `display_name` 当作每个数据集自己的任意展示覆盖。

5. `aliases` / `synonyms` 默认从 dataset 字段和指标删除；只在 dictionary / glossary / metric definition 维护。

6. `business_definition.ref` 优先复用现有结构，不新增 `semantic_ref`。

7. 如果 `name` 找不到 dictionary / mapping / glossary / audit 引用：

   ```yaml
   business_definition:
     source_type: inferred
     needs_review: true
   ```

   不允许假装是 linked 标准语义。

### Chinese semantic name and display resolution rules

`display_name` 是 dataset 字段层保留的语义层中文名，不再作为“可有可无的展示覆盖”。展示层按顺序解析：

```text
dataset display_name
-> dictionary/glossary/metric display_name via business_definition.ref
-> physical_name
-> name
```

`display_name` 和 aliases / synonyms 的边界：

```text
display_name = 一个正式显示标签，例如 客运收入。
aliases/synonyms = 多个可识别叫法，例如 客收、票款收入、旅客运输收入。
```

dataset 层应保留一个正式中文名 `display_name`，但不应复制标准层 aliases / synonyms。别名识别依赖标准层 aliases / synonyms，而不是 dataset 字段内重复维护。

### Alias search compensation

删除 dataset 内 `aliases/synonyms` 后，别名搜索必须由索引层补回来，而不是让 dataset 继续复制别名。

核心设计：

```text
dictionary / glossary / metric aliases
-> metadata index 编译成 alias search records
-> metadata search 命中 alias
-> 回跳 canonical semantic: dataset.name + dataset.display_name + dataset.physical_name + business_definition.ref
-> metadata context 返回 alias_source
-> analysis-plan 使用 canonical semantic 做规划
```

索引层需要新增或强化一种 alias record：

```json
{
  "record_type": "alias",
  "dataset_id": "duckdb.ho.xxx",
  "entity_type": "metric",
  "alias": "客收",
  "canonical_name": "passenger_revenue",
  "canonical_display_name": "客运收入",
  "physical_name": "票款收入",
  "ref": "dictionary:juneyao.metrics:passenger_revenue",
  "alias_source": "dictionary:juneyao.metrics:passenger_revenue"
}
```

实现规则：

1. alias 真源只来自标准层：
   * `metadata/dictionaries/*.yaml`
   * `metadata/glossary` section
   * metric / field definition 中的 `aliases` / `synonyms`
2. dataset 只提供落地关系：
   * `name`：canonical semantic id
   * `display_name`：canonical Chinese name
   * `physical_name`：当前源字段
   * `business_definition.ref`：语义来源
3. index build 时做 join：
   * 用 dataset `business_definition.ref` 或 `name` 找到 dictionary / glossary item。
   * 把该标准项的 aliases/synonyms 编译进 `metadata/index/search.db`。
   * alias record 的 payload 必须保留 `alias_source`，避免把别名误当作物理字段。
4. search 返回时做归一化：
   * 用户搜 `客收`，返回 `passenger_revenue / 客运收入 / 票款收入`。
   * match reason 标记为 `alias`。
   * result 里区分 `matched_alias` 和 `physical_name`。
5. context pack 带回匹配证据：
   * `matched_alias`
   * `alias_source`
   * `canonical_name`
   * `display_name`
   * `physical_name`
   * `ref`

这样用户说“查客收趋势”时，需求理解链路不需要 dataset aliases，也能通过标准层 alias 命中当前 dataset 里的 `passenger_revenue`。

### Source resolution rules

取数字段不要求 dataset 每条都写 `source_field`。执行层按顺序解析：

```text
dataset source_field override
-> mapping.view_field matched by dataset.name / mapping.standard_id
-> dataset physical_name
```

`source_field` 不是“source 的标准表达”。它只是现有执行层可能还需要的临时定位字段。长期目标是：

```text
字段取数靠 physical_name。
源字段到标准语义靠 mapping。
指标实现靠 expression。
source_field 只保留 override / legacy shortcut。
```

指标执行按顺序解析：

```text
metric.expression
-> mapping + dictionary aggregation
-> metric.source_field shortcut
-> metric.physical_name if source has precomputed metric column
```

## Impact List

本任务不是单纯删 YAML 字段。字段面变化会影响以下能力，必须同步修改和验证。

| Area | Impact | Required handling |
| --- | --- | --- |
| 需求理解 / analysis-plan | 用户说“客收、上座率、国内航线”等别名时，规划阶段不能再从 dataset 内 aliases 命中 | `metadata index` 必须把标准层 aliases/synonyms 编译进搜索索引；`metadata context` 必须带回 matched semantic、aliases 来源和 ref |
| 别名识别 | dataset 删除 `aliases/synonyms` 后，不能再靠 dataset 字段召回俗称 | 搜索和意图理解必须读取 dictionary / glossary / metric definition 的 aliases/synonyms |
| 中文展示 | `display_name` 从“展示覆盖”变成“语义层中文名” | 报告、catalog、metadata search 优先用 dataset `display_name`，缺失时从 ref 标准层补齐 |
| 搜索索引 | 删除 dataset aliases 后，索引词会减少 | index 构建时合并 dataset 的 `name/display_name/physical_name` 和 ref 标准层 aliases/synonyms |
| metadata context pack | context 以前可能直接输出 dataset metrics/fields 里的 synonyms/source_field | context 应输出三层：标准语义 `name/display_name`、源字段 `physical_name`、标准层 aliases/synonyms；不把 aliases 回写 dataset |
| Mapping 解析 | dataset 删除 `standard_id` 后，不能从 dataset 字段找标准 ID | 统一用 `dataset.name` 匹配 `mapping.standard_id` |
| 取数执行 | 普通字段删除 `source_field` 后，旧执行链可能找不到字段 | 执行层先兼容读取旧 `source_field`，新生成使用 `physical_name`，并逐步迁移 |
| 指标计算 | 指标 `source_field` 降级后，简单指标不能只靠 shortcut | 优先使用 `expression`；表达式输入字段通过 `name -> physical_name` 或 mapping 解析 |
| 血缘 / lineage | 删除 `source_field` 后，不能再把它当作 lineage 的源字段 | 字段血缘使用 `physical_name`；标准语义血缘使用 `business_definition.ref` / mapping；指标血缘使用 `expression` 的输入字段 |
| metadata reconcile | runtime registry 可能仍保留 display/source 字段旧结构 | reconcile 需兼容旧 registry，同时以 `name/display_name/physical_name/ref` 作为新语义对齐标准 |
| 报告生成 | 报告以前可能用 `display_name/source_field/synonyms` 直接成文 | 改为使用语义中文名 + physical source + ref 解释，不展示内部 alias 列 |
| 导出列名 | 导出中文 header 不能依赖 dataset aliases | 导出层使用 `display_name` 作为正式列名；用户指定别名时只作为导出层 select/header 配置 |
| Validator | 不能再把 `display_name == physical_name` 判定为冗余错误 | 只校验 `display_name` 是否存在且是单值中文语义名；`aliases/synonyms` 留在标准层 |
| Migration | 现有 YAML 可能大量带 `source_field/standard_id/synonyms` | 提供 dry-run cleanup report，区分可自动删除和需要人工确认的字段 |

## Compatibility Plan

为了降低对现有产品的影响，实施必须分两层：先兼容读取，后收紧生成。

1. 读取层兼容旧 YAML：
   * 仍能读取旧 `source_field`、`standard_id`、`synonyms`。
   * 读取时把它们标记为 legacy/cleanup candidate。
   * 不因为旧字段存在而中断现有分析。
2. 生成层采用新 contract：
   * 新 YAML 默认只生成 `name/display_name/physical_name` 三个名称字段。
   * 新 YAML 不再生成普通字段 `source_field`、`standard_id`、dataset aliases/synonyms。
3. 索引层补偿别名召回：
   * `metadata index` 生成 FTS 时，不能只读 dataset。
   * 必须把 `dictionary_refs`、`mapping_ref` 指向的标准层 aliases/synonyms 合并进 search records。
   * 搜索结果 payload 要能说明命中来自 dataset `display_name`、source `physical_name`，还是 standard aliases。
   * alias 命中必须回跳到 canonical semantic，不允许把 alias 当成字段名或物理字段。
4. Context 层补偿分析规划：
   * `metadata context` 需要输出标准语义名、中文语义名、真实源字段、定义 ref、命中别名来源。
   * analysis-plan 不直接依赖 dataset 内 aliases。
   * analysis-plan 只能使用 context 返回的 canonical `name/display_name/physical_name`，不能直接拿 `matched_alias` 生成 SQL。
5. 血缘层补偿：
   * 字段级血缘：`dataset.source.object + physical_name`。
   * 语义级血缘：`dataset.name + business_definition.ref`。
   * 指标级血缘：`metrics.expression` 解析出的字段输入；无法解析时才读取 legacy `source_field`。
6. 发布策略：
   * 第一版只加 validator warning、cleanup report 和新生成规则。
   * 第二版再把 dataset 字段层 `standard_id` strict fail。
   * `source_field` 先 warning，再按执行链迁移情况收紧。

## Migration Strategy

1. 第一阶段只改 contract、生成器和 validator，不批量改用户业务 YAML。
2. 新生成 dataset 字段默认输出：

   ```yaml
   name: route_segment
   display_name: 航段
   physical_name: 航段
   ```

3. 新生成 dataset 字段默认不输出：

   ```yaml
   standard_id
   source_field
   aliases
   synonyms
   ```

4. 对旧 YAML 生成 cleanup report：
   * `standard_id`：迁移到 mapping 或删除。
   * 普通字段 `source_field`：若等于 `physical_name`，可自动删除；若不同，标记为 override 待确认。
   * `aliases/synonyms`：迁移到 dictionary / glossary / metric definition。
   * `display_name`：保留为语义层中文名；如果为空，从标准层或 `physical_name` 补齐。
5. 修改搜索/index/report/export 时，必须验证删除 aliases/source_field 后仍能召回中文、俗称和真实字段。

## Implementation Scope

### Files likely impacted

* `skills/metadata/references/yaml-structure-contract.md`
* `skills/metadata/SKILL.md`
* `skills/metadata/scripts/validate_metadata.py`
* `skills/metadata/scripts/enrich_definitions.py`
* `skills/metadata/scripts/sync_registry.py`
* `skills/metadata/lib/semantic_definitions.py`
* `skills/metadata/lib/metadata_completeness.py`
* `skills/metadata/lib/metadata_index.py`
* `skills/metadata/lib/metadata_context.py`
* `skills/metadata-report/scripts/report_context.py`
* `docs/metadata-lookup-workflow.md`
* `skills/analysis-plan/README.md`
* `schemas/metadata_dataset.schema.json`
* tests covering metadata validation / report context / registry sync

### Required changes

1. Update YAML contract:
   * 明确 dataset 字段层不常规维护 `standard_id`。
   * 明确普通字段默认删除 `source_field`，它只是 legacy/override。
   * 明确普通字段默认保留 `display_name`，但它表示语义层中文名，不是 physical name 的重复仓库。
   * 明确普通字段/指标默认删除 `aliases` / `synonyms`，这些属于标准语义层。
   * 明确 `business_definition.ref` 负责证明 `name` 是否 linked。

2. Update generator/normalizer:
   * 生成 dataset YAML 时默认不输出：
     * `standard_id`
     * 普通字段的 `source_field`
     * 普通字段/指标的 `aliases` / `synonyms`
   * 生成 dataset YAML 时默认输出并补齐：
     * `display_name` 作为语义层中文名
   * 迁移或 lint 时列出可删除字段：
     * `source_field == physical_name`
     * `standard_id == name`
     * dataset aliases / synonyms
   * 若 `name` 由 AI/LLM 推断且无 ref，写 `source_type: inferred` + `needs_review: true`。

3. Update validation:
   * dataset 字段层出现 `standard_id` 时 strict error。
   * 普通字段出现 `source_field` 时 warning；`source_field == physical_name` 时 strict cleanup finding。
   * 普通字段缺少 `display_name` 时 warning 或 fail；`display_name == physical_name` 允许，但必须解释为语义中文名。
   * 普通字段/指标出现 `aliases` / `synonyms` 时 warning，提示迁移到 dictionary / glossary。
   * `business_definition.ref` 指向 mapping/dictionary 时，校验 ref target 是否存在。
   * 若 `source_type` 声称 dictionary/mapping，但 ref 不存在，fail。
   * 若 `name` 不符合 stable semantic ID，fail。

4. Update report/runtime resolution:
   * 报告展示字段名时使用 display resolution rules。
   * 取数/registry 生成时使用 source resolution rules。
   * 不因 dataset 删除 `source_field/aliases` 而丢失展示、别名召回或执行能力。

5. Update metadata lookup and analysis context:
   * `metadata index` 需要从 dictionary / glossary / metric definition 合并 aliases/synonyms。
   * `metadata index` 需要生成 alias record 或等价 payload，字段包含 `matched_alias`、`alias_source`、`canonical_name`、`canonical_display_name`、`physical_name`、`ref`。
   * `metadata search` 结果需要标明命中来源，避免把 alias 当成 dataset 字段事实。
   * `metadata context` 需要返回标准语义、中文语义名、真实源字段、ref 和 alias source。
   * analysis-plan 使用 context 中的 semantic/display/physical 三层信息，不直接依赖 dataset aliases/source_field。

6. Update lineage handling:
   * 字段 lineage 使用 `source.object + physical_name`。
   * 语义 lineage 使用 `name + business_definition.ref`。
   * 指标 lineage 使用 `expression` 输入字段；legacy `source_field` 只做 fallback。

7. Migration helper:
   * 增加 dry-run 检查或修复脚本，列出可删除的名称字段：
     * `standard_id`
     * 普通字段的 `source_field`
     * 普通字段/指标的 `aliases` / `synonyms`
   * 标出特别确定可删的重复项：
     * `source_field == physical_name`
     * `standard_id == name`
   * 输出建议 diff 或 report，不默认批量改业务 YAML。

## Acceptance Criteria

* [ ] PRD 中的“减少字段数量”目标写入正式 YAML contract。
* [ ] dataset 字段层默认不输出 `standard_id`。
* [ ] 普通字段默认不输出 `source_field`。
* [ ] 普通字段默认输出 `display_name`，且定义为语义层中文名。
* [ ] 普通字段/指标默认不输出 `aliases` / `synonyms`。
* [ ] 迁移检查能识别 `source_field == physical_name` 为可删除字段。
* [ ] 迁移检查不会把 `display_name == physical_name` 误判为必须删除；它可以表示“源字段名刚好等于语义中文名”。
* [ ] `business_definition.ref` 被明确用于证明 `name` 是否 linked。
* [ ] `name` 无真实 ref 时必须标记 `source_type: inferred/pending` 或 `needs_review: true`。
* [ ] report / registry / sync 逻辑在删除 `source_field/aliases` 后仍能按 fallback 正常工作。
* [ ] 搜索/index 能通过标准层 aliases/synonyms 召回俗称，不依赖 dataset 内 aliases/synonyms。
* [ ] 需求理解阶段的 `metadata search -> metadata context -> analysis-plan` 能用别名命中标准指标，并在 context 中说明 alias 来源。
* [ ] 用户搜 `客收` 这类别名时，search 返回 canonical metric，并明确 `matched_alias=客收`、`canonical_name=passenger_revenue`、`display_name=客运收入`、`physical_name=<当前数据源字段>`。
* [ ] analysis-plan 不允许把 `matched_alias` 当作 SQL 字段，只能使用 context 中的 canonical/physical 解析结果。
* [ ] 字段/指标血缘不依赖 dataset `source_field`；字段血缘用 `physical_name`，指标血缘用 `expression` 输入字段。
* [ ] 旧 YAML 仍可读，新的 generator 不再写被删除字段。
* [ ] 有测试覆盖：
  * `standard_id` 不应出现在 dataset 字段层。
  * 普通字段不应常规输出 `source_field`。
  * 普通字段应保留语义层中文名 `display_name`。
  * dataset 字段/指标不应复制标准层 aliases / synonyms。
  * dictionary/glossary aliases 能进入 search index 并命中用户俗称。
  * alias search result 能回跳到 canonical name/display_name/physical_name/ref。
  * context pack 能返回 semantic name、display name、physical name、ref 和 alias source。
  * lineage 能从 physical_name / expression 生成，不依赖 source_field。
  * `ref` 不存在但声明 linked 时失败。
  * 删除 source/aliases 后报告、搜索和 registry 仍能解析。
* [ ] 提供至少一个 before/after 示例，说明如何把四字段重复 YAML 收敛成最小结构。

## Example Before / After

Before:

```yaml
fields:
  - name: segment
    physical_name: 航段
    display_name: 航段
    standard_id: route
    source_field: 航段
    role: dimension
    type: category
```

After:

```yaml
fields:
  - name: route_segment
    display_name: 航段
    physical_name: 航段
    role: dimension
    type: category
    business_definition:
      text: 航班经营中的航段维度。
      source_type: mapping
      ref: mapping:duckdb.ho.dim_ho_flight_type.mapping:route_segment
      confidence: 0.8
      needs_review: false
```

If no real ref exists yet:

```yaml
fields:
  - name: route_segment
    display_name: 航段
    physical_name: 航段
    role: dimension
    type: category
    business_definition:
      text: 航段字段，标准语义待确认。
      source_type: inferred
      confidence: 0.5
      needs_review: true
```

## Out of Scope

* 不在本任务中批量改所有现有业务 dataset YAML。
* 不新增 `semantic_ref` 字段，优先复用 `business_definition.ref`。
* 不把 mapping / dictionary / registry 合并进 dataset。
* 不改变已有 runtime registry 的存储模型，除非执行层需要 fallback 解析。
* 不处理导出 CSV 表头中文化；那仍属于 `RA:data-export`。

## Technical Notes

* Existing field identity contract: `skills/metadata/references/yaml-structure-contract.md`
* Existing validator: `skills/metadata/scripts/validate_metadata.py`
* Existing enrichment logic: `skills/metadata/scripts/enrich_definitions.py`
* Existing registry sync fallback currently looks at `source_field -> physical_name -> display_name -> name` in `skills/metadata/scripts/sync_registry.py`; implementation must avoid relying on redundant YAML to preserve behavior.
* Related prior task: `.trellis/tasks/05-08-open-source-usage-guardrails/prd.md`

## Definition of Done

* Contract updated.
* Generator / normalizer updated where relevant.
* Validator warnings/errors added.
* Report / registry fallback behavior verified.
* Tests added or updated.
* Migration/report helper available for existing YAML cleanup.
