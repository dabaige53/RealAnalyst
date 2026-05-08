# YAML Structure Contract

## Directory Roles

`metadata/` uses separate layers. Do not collapse them into one large YAML file.

```text
metadata/
├── sources/        # source materials and audit evidence
├── dictionaries/   # shared metrics, dimensions, glossary
├── mappings/       # source fields to standard semantics
├── datasets/       # one real analyzable source per YAML
├── index/          # generated JSONL indexes
└── sync/           # connector discovery snapshots
```

## sources/

Store original user-provided files, exported reports, connector discovery snapshots, and migration inputs.

Rules:

- Do not treat sources as datasets.
- Do not edit source files to fit a schema.
- YAML maintained elsewhere should cite project-local source paths such as `metadata/sources/<file>`, not a user Downloads path.

## dictionaries/

Dictionary files are shared semantic definitions. They are indexed, but they are not valid dataset context targets.

Common files:

```text
metadata/dictionaries/metrics.yaml
metadata/dictionaries/dimensions.yaml
metadata/dictionaries/glossary.yaml
```

Required top-level keys:

```yaml
version: 1
id: juneyao.metrics
kind: dictionary
display_name: 吉祥航空公共指标字典
source_evidence:
  - type: document
    source: metadata/sources/source.md
    quote: Evidence summary.
metrics: []
fields: []
glossary: []
```

Only include the payload list that fits the file. For example, `metrics.yaml` may contain only `metrics`.

Metric item shape:

```yaml
- name: load_factor
  display_name: 客座率
  expression: Σ RPK_i / Σ ASK_i × 100
  aggregation: weighted_avg
  unit: "%"
  category: efficiency
  metric_group: efficiency
  direction: higher_better
  benchmark: ""
  description: 旅客客公里与可提供座位公里数之比。
  synonyms: [LF, PLF, 上座率]
  business_definition:
    text: 旅客客公里与可提供座位公里数之比。
    source_type: dictionary
    confidence: 0.85
    source_evidence:
      - type: document
        source: metadata/sources/source.md
        quote: 客座率定义。
    needs_review: false
```

Field item shape:

```yaml
- name: flight_date
  physical_name: FlightDate
  display_name: 航班日期
  role: dimension
  type: date
  description: 航班执行日期。
  dimension_group: flight
  synonyms: [FlightDate, 航班日期]
  enum_values: []
  labels: ""
  lookup: ""
  sensitive_level: internal
  business_definition:
    text: 航班执行日期。
    source_type: user_confirmed
    confidence: 0.8
    source_evidence:
      - type: document
        source: metadata/sources/source.md
        quote: 航班日期字段。
    needs_review: false
```

Glossary item shape:

```yaml
- section: airlines
  key: HO
  display_name: 吉祥航空
  english_name: Juneyao Airlines
  type: 民营航司
  synonyms: []
  definition: 吉祥航空。
  formula: ""
  unit: ""
  values: [PVG, SHA]
  business_definition:
    text: 吉祥航空。
    source_type: dictionary
    confidence: 0.85
    source_evidence:
      - type: document
        source: metadata/sources/source.md
        quote: 航司词表。
    needs_review: false
```

## mappings/

Mapping files connect a source field to a standard metric or dimension. They should not contain full public metric dictionaries.

Required shape:

```yaml
version: 1
id: tableau.sales.agent.mapping
kind: mapping
source_id: tableau.sales.agent
display_name: 代理人销售字段映射
source_evidence:
  - type: document
    source: metadata/sources/source.md
    quote: 字段映射表。
mappings:
  - type: metric
    view_field: 客票量
    standard_id: pax
    field_id_or_override: 客票量
    definition_override: 当前销售视图中的客票量字段，按代理销售口径统计。
    notes: ""
```

`type` must be `metric`, `dimension`, or `field`.

## datasets/

Dataset files describe real analyzable sources only: a Tableau view/workbook, DuckDB table/view, CSV file, Excel sheet, or similar source.

Required shape:

```yaml
version: 1
id: tableau.sales.agent
display_name: AI分析用_代理人销售报表
description: 数据源说明。
source:
  connector: tableau
  object: tableau.sales.agent
  source_id: tableau.sales.agent
business:
  domain: sales
  description: 代理人销售分析数据源。
  grain: [source_defined]
  primary_key: []
  time_fields: []
  suitable_for: []
  not_suitable_for: []
  sample_questions: []
maintenance:
  owner: RealAnalyst LLM metadata
  last_updated: "2026-04-29"
  pending_questions: []
dictionary_refs:
  - juneyao.metrics
mapping_ref: tableau.sales.agent.mapping
fields: []
metrics: []
relationships: []
```

Datasets may reference dictionaries and mappings. They should not duplicate full public dictionaries.

Dataset YAML is a semantic entry, not a profile store, enum store, mapping file, or registry snapshot.

Field identity rules:

- `fields[].name` is the stable semantic identifier. Prefer snake_case or dotted ASCII identifiers.
- User-facing Chinese names belong in `display_name`.
- Physical source columns belong in `physical_name` or `source_field`.
- Export-only CSV header translation must be handled by `RA:data-export`; it must not rewrite dataset field identities.

Example:

```yaml
fields:
  - name: flight_type
    physical_name: FlightType
    display_name: 航班性质
    role: dimension
    type: string
    description: 航班性质分类字段。
    business_definition:
      text: 航班在业务统计中的性质分类。
      source_type: mapping_override
      ref: mapping:duckdb.ho.flight_results.mapping:FlightType
      confidence: 0.8
      needs_review: false
```

Do not write these keys anywhere in `metadata/datasets/*.yaml`:

- `sample_profile`
- `sample_values`
- `top_values`
- `enum_values`
- `source_mapping`
- `definition_source`
- `duckdb_type`
- `nullable`

Dataset field and metric definitions must use `business_definition.ref` to point to dictionary, mapping, or audit evidence. Do not expand `source_evidence`, `quote`, `source`, or document paths into dataset field/metric definitions.

Move source field mappings to `metadata/mappings/*.yaml`. Move sample values, profile summaries, enum candidates, nullable flags, physical type snapshots, and registry data to `metadata/sources/refine/`, connector snapshots, or `runtime/registry.db`. Keep change logs, relation records, review trails, and diff reports in `metadata/audit/`.

Metrics are formal analysis measures. Do not register a metric whose `business_definition.source_type` is `pending`; keep that item as a field, refine suggestion, or metadata gap until the metric has a usable definition.

`description` is a short human summary. `business_definition.text` is the structured definition. They must not be identical.

`metadata validate` enforces this responsibility boundary. A dataset YAML over 1000 lines produces a warning; over 1500 lines is treated as a failed boundary check because it usually means profile, enum, mapping, registry, or repeated evidence data has leaked into the semantic layer.

## index/

Generated only. Do not hand-edit:

```text
datasets.jsonl
fields.jsonl
metrics.jsonl
glossary.jsonl
mappings.jsonl
```
