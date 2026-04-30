# Architecture

RealAnalyst 有两条主线：注册元数据线和实施分析线。前者把 Tableau / DuckDB 的 source facts 沉淀成可审查的 metadata；后者基于 metadata 完成 plan、export、profile、report 和 verify。

## Two Flow Lines

```mermaid
flowchart LR
    subgraph Register["注册元数据线"]
        Sync["connector sync<br/>Tableau / DuckDB"] --> Sources["metadata/sources<br/>evidence"]
        Sources --> YAML["metadata YAML<br/>dictionaries / mappings / datasets"]
        YAML --> Validate["metadata validate"]
        Validate --> Index["metadata index<br/>JSONL + search.db (FTS5)"]
        Index --> Catalog["metadata catalog<br/>lightweight dataset summary"]
        Index --> Search["metadata search<br/>FTS5 BM25 ranking"]
        Search --> Context["metadata context<br/>single or multi-dataset pack"]
        Catalog --> Context
        YAML --> Reconcile["metadata reconcile<br/>compare runtime vs metadata"]
    end

    subgraph Run["实施分析线"]
        Request["business request"] --> Plan["analysis-plan"]
        Plan --> Export["data-export<br/>controlled CSV"]
        Export --> Fusion["artifact-fusion<br/>source group merge"]
        Fusion --> Profile["data-profile"]
        Profile --> Report["report"]
        Report --> Verify["report-verify"]
        Verify --> Delivery["reviewable delivery"]
    end

    Context --> Plan
```

## File Responsibilities

```mermaid
flowchart TD
    Dictionaries["metadata/dictionaries/*.yaml<br/>shared semantics"] --> IndexFile["metadata/index/*.jsonl<br/>generated lookup index"]
    Mappings["metadata/mappings/*.yaml<br/>source field mappings"] --> IndexFile
    Dataset["metadata/datasets/*.yaml<br/>real source metadata"] --> IndexFile
    IndexFile --> FTS5["metadata/index/search.db<br/>FTS5 full-text index"]
    Dictionaries --> ContextJson["metadata context JSON<br/>single or multi-dataset pack"]
    Mappings --> ContextJson
    Dataset --> ContextJson
    Registry["runtime/registry.db<br/>source registry + lookup tables + source_groups"] --> ExportScript["data-export scripts"]
    ContextJson --> PlanDoc["jobs/{SESSION_ID}/.meta/analysis_plan.md"]
    ExportScript --> JobData["jobs/{SESSION_ID}/<br/>CSV / summary / manifest"]
    JobData --> ProfileJson["profile manifest / profile json"]
    PlanDoc --> ReportMd["report Markdown"]
    ProfileJson --> ReportMd
    ReportMd --> Verification["verification.json"]
```

`runtime/registry.db` 是唯一运行时 SQLite DB；其中 `source_groups` 管理 1 个 primary source 与最多 2 个 supplementary sources，供 `artifact-fusion` 做多源合并。

## Public Repository Boundary

```mermaid
flowchart LR
    Public["Public repo"] --> Demo["demo metadata<br/>example CSV<br/>README / docs<br/>schemas / scripts"]
    Local["Local private state"] --> Env[".env"]
    Local --> DB["*.duckdb / *.db / registry.db"]
    Local --> Jobs["jobs/ logs/ exports"]
    Local --> Sync["real connector snapshots"]

    Demo -.-> Safe["safe to commit"]
    Env -.-> Ignored["ignored by .gitignore"]
    DB -.-> Ignored
    Jobs -.-> Ignored
    Sync -.-> Ignored
```
