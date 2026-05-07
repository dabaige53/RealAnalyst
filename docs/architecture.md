# Architecture

RealAnalyst 是平台无关的 metadata-first 分析执行系统。Codex skills 是当前第一套 adapter / entrypoint；核心能力由 Metadata Core、Runtime Registry Core 和 Job Core 承接，未来可以被 CLI、MCP、其他 LLM 产品、企业 agent workflow 或 BI workflow 复用。

## Three Core Model

| Core | 管什么 | 主要路径 |
| --- | --- | --- |
| Metadata Core | 业务含义、definition state、evidence relation、index/context builder | `metadata/`、`skills/metadata/`、`skills/metadata-search/` |
| Runtime Registry Core | source registry、connector metadata、filter / parameter / source group | `runtime/registry.db`、`runtime/`、`skills/data-export/` |
| Job Core | 单次分析状态、artifact index、feedback、verification artifacts | `jobs/{SESSION_ID}/`、`skills/analysis-run/`、`skills/report-verify/` |

核心边界：Metadata 管“含义”，Registry 管“能不能取”，Job 管“这次实际用了什么”。Report 是 `RA:analysis-run` 面向用户的最终交付，不是独立 core。Job 内部保留完整上下文，包括 plan、export、profile、analysis、verification、definition snapshot、feedback 和 artifact index。

LLM 负责组织、推断、解释和编排；事实状态由三核承接。LLM 可以起草定义、组织证据、生成计划、写报告、发现口径缺口和整理 refine 材料，但不能把推断定义直接标成事实，不能隐式写回正式 metadata，不能用聊天记忆替代 job artifacts。

长期任务管理不属于 Job Core；跨多天目标、阶段推进和用户意图演进交给外部 continuity layer。

## Core Flow

```mermaid
flowchart LR
    subgraph Metadata["Metadata Core<br/>含义"]
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

    subgraph Registry["Runtime Registry Core<br/>能不能取"]
        RegDb["runtime/registry.db<br/>source / fields / filters / parameters / groups"] --> Export["data-export<br/>controlled CSV"]
    end

    subgraph Job["Job Core<br/>本次实际用了什么"]
        Request["business request"] --> Router["RA:getting-started<br/>skill router"]
        Router -->|unregistered| MetadataEntry["RA:metadata<br/>minimum registration"]
        Router -->|ready| Run["RA:analysis-run<br/>formal analysis"]
        MetadataEntry --> Run
        Run --> Plan["analysis-plan"]
        Run --> Export
        Export --> Fusion["artifact-fusion<br/>source group merge"]
        Fusion --> Profile["data-profile"]
        Profile --> Analysis["analysis.json"]
        Analysis --> Report["report"]
        Report --> Verify["report-verify"]
        Verify --> Delivery["reviewable delivery"]
        Analysis -.-> Feedback["metadata_feedback.jsonl"]
    end

    Context --> Run
    YAML --> RegDb
    Feedback -.-> Refine["metadata-refine<br/>修正材料"]
    Refine -.-> Maintenance["RA:metadata<br/>用户主动维护"]
    Maintenance --> YAML
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
    JobData -.-> Feedback["metadata_feedback.jsonl"]
    Feedback --> RefinePack["metadata/sources/refine/{id}/<br/>refine reference pack"]
    RefinePack --> Maintenance2["RA:metadata<br/>user-confirmed writeback"]
    Maintenance2 --> Dataset
    Dataset --> AuditLog["metadata/audit/<br/>changes + change_report"]
```

`runtime/registry.db` 是唯一运行时 SQLite DB；其中 `source_groups` 管理 1 个 primary source 与最多 2 个 supplementary sources，供 `artifact-fusion` 做多源合并。

`metadata/audit/` 记录每次 YAML 维护的变更摘要、文件路径和证据，并可生成变更报告。

Dataset YAML 必须轻量：只放数据集身份、可分析字段/指标、边界和引用关系。profile、sample values、enum values、registry snapshot、report 结论和证据全文分别归到 `metadata/sources/`、`runtime/registry.db`、`metadata/audit/` 或 job artifacts，不回写到 dataset YAML。

`RA:metadata-refine` 只生成参考材料；正式 YAML 写回必须由用户主动进入 `RA:metadata`，并经过 validate / index / sync-registry。

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
