# Architecture

RealAnalyst 有两条主线：注册元数据线和实施分析线。前者把 Tableau / DuckDB 的 source facts 沉淀成可审查的 metadata；后者基于 metadata 完成 plan、export、profile、report 和 verify。

## Two Flow Lines

```mermaid
flowchart LR
    subgraph Register["注册元数据线"]
        Sync["connector sync<br/>Tableau / DuckDB"] --> Sources["metadata/sources<br/>evidence"]
        Sources --> YAML["metadata YAML<br/>dictionaries / mappings / datasets"]
        YAML --> Validate["metadata validate"]
        Validate --> Index["metadata index"]
        Index --> Context["metadata context<br/>minimal context pack"]
    end

    subgraph Run["实施分析线"]
        Request["business request"] --> Plan["analysis-plan"]
        Plan --> Export["data-export<br/>controlled CSV"]
        Export --> Profile["data-profile"]
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
    Dataset --> ContextJson["metadata context JSON<br/>planning input"]
    Registry["runtime/**/registry.db<br/>local execution registry"] --> ExportScript["data-export scripts"]
    ContextJson --> PlanDoc["jobs/{SESSION_ID}/.meta/analysis_plan.md"]
    ExportScript --> JobData["jobs/{SESSION_ID}/<br/>CSV / summary / manifest"]
    JobData --> ProfileJson["profile manifest / profile json"]
    PlanDoc --> ReportMd["report Markdown"]
    ProfileJson --> ReportMd
    ReportMd --> Verification["verification.json"]
```

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
