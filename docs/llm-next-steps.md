# RealAnalyst LLM Next Steps

这份文档给安装后的 LLM 读取。目标是先用 `RA:getting-started` 做轻量 guide + skill router + minimal status check，再按用户目标进入 metadata 注册、正式分析或口径说明；不要在安装后立刻创建目录。

## 先对用户这样说

```text
RealAnalyst 已经装好，并且只在当前项目启用。当前项目只新增了插件入口、skills 和 runtime support；没有创建 metadata、jobs、logs、真实 registry 或 demo 数据。下一步先从 RA:getting-started 开始，我会做最小状态检查，再判断应该进入 metadata 注册、正式分析、口径说明或报告验证。
```

然后让用户选择：

1. 已经有 Tableau 报表 / workbook。
2. 已经有 DuckDB / 数据库 / CSV / Excel。
3. 已经有注册好的 metadata / registry，想做正式分析。
4. 暂时没有数据源，只想先整理字段、指标和术语。
5. 想查看已有数据集口径说明、归档分析后的口径问题，或验证已有报告。

## 不要做什么

- 不要在安装检查阶段创建 `metadata/`、`jobs/`、`logs/`、`runtime/registry.db` 或任何业务运行产物。
- `runtime/` 支持文件由安装器维护；不要手工复制、改名或分散到其他目录。
- 不要写当前项目的 `.env` 或 `.gitignore`。
- 不要把 demo 数据写进用户项目。
- 不要让用户把密钥写进 README、聊天记录或仓库文件。
- 只有用户确认要保存抽取结果或执行分析时，才按需创建项目文件。

## `.env` 填写

安装脚本会在插件目录初始化 `.env`，通常是：

```text
~/plugins/realanalyst/.env
```

如果用户要接 Tableau，引导用户在这个文件里填写：

```text
TABLEAU_BASE_URL=https://your-tableau-server
TABLEAU_SITE_ID=your-site-id
TABLEAU_PAT_NAME=your-personal-access-token-name
TABLEAU_PAT_SECRET=your-personal-access-token-secret
```

说明：

- `TABLEAU_BASE_URL`：Tableau Server / Cloud 根地址。
- `TABLEAU_SITE_ID`：站点 ID；默认站点通常可以留空，但要让用户确认。
- `TABLEAU_PAT_NAME`：Tableau Personal Access Token 名称。
- `TABLEAU_PAT_SECRET`：Token secret，只放本机 `.env`，不要提交。

填完后，再问用户要抽取哪个 workbook / view / dashboard。不要一上来全量扫描。

## Skills 快速入口

### 默认入口

```text
/skill RA:getting-started
帮我做最小状态检查，判断应该先注册 metadata、进入正式分析、查看口径说明、归档口径问题，还是验证已有报告。
```

`RA:getting-started` 是默认 skill router。它只检查当前项目是否已有 metadata / registry / dataset，识别用户给的是 Tableau、DuckDB、CSV、文档还是口径说明，并输出一条可复制的下一步 `/skill` 调用指令。它不创建正式 analysis job，不执行取数，不生成业务报告，不自动注册正式 metadata。

### 整理元数据

```text
/skill RA:metadata
我有一个数据源需要整理 metadata。请先问我要来源、字段、指标、筛选器和证据，不要直接创建文件。
```

### 整理指标口径

```text
/skill RA:metadata
帮我整理这些指标的业务口径：指标名称、计算公式、单位、粒度、适用范围、证据和待确认问题。
```

### 整理术语表

```text
/skill RA:metadata
帮我把这些业务术语整理成 glossary，包含中文名、英文名、同义词、定义、来源证据和是否需要 review。
```

### 从 Tableau 抽取 metadata

```text
/skill RA:metadata
我要从 Tableau workbook 抽取字段、筛选器、参数和指标口径。请先检查 .env 需要哪些信息，再问我要 workbook/view/dashboard 名称。
```

### 从 DuckDB / CSV / Excel 抽取 metadata

```text
/skill RA:metadata
我要从本地 DuckDB/CSV/Excel 抽取字段和指标口径。请先问我要文件路径、表名或 sheet 名、关键字段和分析目标。
```

### 整理分析后的 metadata 修正材料

```text
/skill RA:metadata-refine
请读取当前 job 的 metadata feedback、profile 和必要的真实数据样本，生成可归档到 metadata/sources/refine/ 的修正参考材料，并在 refine_followup.md 里写清本次做了什么、后续建议和待确认问题。不要直接修改正式 YAML。
```

### 执行完整分析

```text
/skill RA:analysis-run
基于已确认的 metadata 和 registry，帮我执行正式完整分析。先生成计划并等我确认，再执行取数、画像、分析、报告和验证。
```

### 查看数据集长期口径说明

```text
/skill RA:metadata-report
帮我生成这个 dataset 的长期口径说明，列出字段、指标、筛选入口、使用边界和待补齐项。
```

### 检查已有报告

```text
/skill RA:report-verify
帮我验证这份报告是否可交付，重点检查数据来源、口径状态、结论证据和待复核项。
```

流程内 skill 不作为普通用户第一层入口：`RA:analysis-plan`、`RA:data-export`、`RA:data-profile`、`RA:report` 通常由 `RA:analysis-run` 编排。`RA:metadata-search` 只在用户明确想查字段/指标/术语/dataset 是否已维护时使用；`RA:artifact-fusion`、`RA:analysis-reference` 是高级/流程内工具；`RA:reference-lookup` 仅作 legacy compatibility entrypoint。

## 安装检查

- 确认 `.agents/plugins/marketplace.json` 包含 `realanalyst`。
- 确认 `.agents/skills/getting-started/SKILL.md` 存在。
- 确认 `.agents/skills/metadata/SKILL.md` 存在。
- 确认 `runtime/paths.py` 和 `runtime/tableau/query_registry.py` 存在。
- 确认安装没有创建 `metadata/`、`jobs/`、`logs/`、`runtime/registry.db` 或 demo 数据。

## 给用户的下一句

```text
你现在是想先注册 metadata、基于已有数据做正式分析、查看数据集口径说明，还是验证已有报告？我会先做最小状态检查，再给你一条可直接执行的下一步 /skill 指令。
```
