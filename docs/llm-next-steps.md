# RealAnalyst LLM Next Steps

这份文档给安装后的 LLM 读取。目标是引导用户抽取和整理元数据，而不是在安装后立刻创建目录。

## 先对用户这样说

```text
RealAnalyst 已经装好，并且只在当前项目启用。当前项目只新增了插件入口、skills 和 runtime support；没有创建 metadata、jobs、logs、真实 registry 或 demo 数据。下一步我们先确认你要从哪里抽取元数据，再决定是否需要保存到项目里。
```

然后让用户选择：

1. 已经有 Tableau 报表 / workbook。
2. 已经有 DuckDB / 数据库 / CSV / Excel。
3. 暂时没有数据源，只想先整理字段、指标和术语。

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

### 先开始

```text
/skill RA:getting-started
帮我确认数据源类型，并列出抽取元数据前需要准备的信息。
```

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

### 生成分析计划

```text
/skill RA:analysis-plan
基于已经整理好的 metadata，帮我生成分析计划。先列出需要确认的数据源、指标、维度、筛选条件和风险。
```

### 执行完整分析

```text
/skill RA:analysis-run
基于已确认的 metadata 和分析计划，帮我执行取数、画像、分析和报告。每一步都保留证据和产物路径。
```

## 安装检查

- 确认 `.agents/plugins/marketplace.json` 包含 `realanalyst`。
- 确认 `.agents/skills/getting-started/SKILL.md` 存在。
- 确认 `.agents/skills/metadata/SKILL.md` 存在。
- 确认 `runtime/paths.py` 和 `runtime/tableau/query_registry.py` 存在。
- 确认安装没有创建 `metadata/`、`jobs/`、`logs/`、`runtime/registry.db` 或 demo 数据。

## 给用户的下一句

```text
你现在是想从 Tableau、DuckDB、CSV/Excel 里抽取元数据，还是先手工整理字段、指标和术语？我会先确认数据源和范围，再决定是否需要写入项目文件。
```
