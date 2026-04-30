# Install RealAnalyst for Codex

RealAnalyst 是 Codex plugin。默认安装为“当前项目启用”，不会在所有项目里自动启动。

## Enable In Current Project

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 -
```

这条命令会自动完成：

- clone / update `https://github.com/dabaige53/RealAnalyst`
- 写入版本策略；默认 `latest`，表示跟随 `main` 最新版本
- 安装到 `~/plugins/realanalyst`
- 创建 `.venv` 并安装 Python dependencies
- 写入当前项目的 `.agents/plugins/marketplace.json`
- 安装项目内 skills 到 `.agents/skills/`
- 安装或更新项目内 `runtime/` 执行支持文件（不复制 `registry.db`、缓存或本地生成数据）
- 初始化插件目录里的 `~/plugins/realanalyst/.env`，已有则保留
- 校验 `.codex-plugin/plugin.json`
- 校验插件仓库 demo metadata

它不会创建 `metadata/`、`jobs/`、`logs/`，不会写当前项目的 `.env` / `.gitignore`，也不会写入 demo 数据或真实 registry。只有用户确认要保存抽取结果或执行分析产物时，RealAnalyst 才会按需创建业务工作区文件夹。

## Version Strategy

默认策略是 `latest`。安装器会把策略写入：

```text
~/plugins/realanalyst/.realanalyst-install.json
```

`latest` 表示每次运行安装器时都更新到 `main` 最新版本：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --version latest
```

如果你希望项目稳定在某个发布版，指定版本号即可。`0.3.4` 和 `v0.3.4` 都可以：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --version 0.3.4
```

以后重新运行安装器且不传 `--version` 时，会优先沿用上次保存的版本策略。

LLM 引导文件读线上文档：`https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/llm-next-steps.md`。不要把引导文件写进用户项目。

完成后重启 Codex，然后输入：

```text
/skill RA:getting-started
帮我确认数据源类型，并列出抽取元数据前需要准备的信息。
```

## Enable In Another Project

在任意目录执行都可以指定目标项目：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --project /path/to/your/project
```

这样 RealAnalyst 只会写入：

```text
/path/to/your/project/.agents/plugins/marketplace.json
/path/to/your/project/.agents/skills/
/path/to/your/project/runtime/
~/plugins/realanalyst/.env
```

不会影响其他项目。

## Enable Globally

如果你确实希望所有 Codex 项目都能看到 RealAnalyst：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --global
```

这会写入：

```text
~/.agents/plugins/marketplace.json
```

全局启用不会安装某个项目的 `.agents/skills/`，也不会初始化项目目录。如果你要让某个项目直接可用，优先使用默认安装或 `--project /path/to/project`。

## Manual Install

如果你不想用一键命令，也可以手动安装：

```bash
mkdir -p ~/plugins
git clone https://github.com/dabaige53/RealAnalyst.git ~/plugins/realanalyst
cd ~/plugins/realanalyst
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m json.tool .codex-plugin/plugin.json
python3 skills/metadata/scripts/metadata.py validate
```

然后在目标项目的 `.agents/plugins/marketplace.json` 里加入这段：

```json
{
  "name": "realanalyst",
  "source": {
    "source": "local",
    "path": "/Users/you/plugins/realanalyst"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

再把 skills 和 runtime support 安装到目标项目：

```bash
mkdir -p /path/to/your/project/.agents/skills
cp -R ~/plugins/realanalyst/skills/* /path/to/your/project/.agents/skills/
cp -R ~/plugins/realanalyst/runtime /path/to/your/project/runtime
```

## Use It

安装完成后，目标项目只包含 `.agents/plugins/marketplace.json`、`.agents/skills/` 和 `runtime/` 支持文件。它仍然是干净项目，不包含 demo 数据集、真实 registry，也不包含 RealAnalyst 业务工作区目录。

LLM 应先读取：

```text
https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/llm-next-steps.md
```

第一次使用：

```text
/skill RA:getting-started
帮我确认数据源类型，并列出抽取元数据前需要准备的信息。
```

维护 metadata：

```text
/skill RA:metadata
帮我注册一个数据集，并维护字段、指标、筛选器和业务口径。
```

执行完整分析：

```text
/skill RA:analysis-run
基于现有 metadata context，帮我生成分析计划，确认后再执行取数、画像、分析和报告。
```

## Connect Tableau

如需连接真实 Tableau，在 `~/plugins/realanalyst/.env` 填写：

```text
TABLEAU_BASE_URL=
TABLEAU_SITE_ID=
TABLEAU_PAT_NAME=
TABLEAU_PAT_SECRET=
```

不要把 `.env` 提交到公开仓库。

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Codex 看不到插件 | 重启 Codex，并检查当前项目 `.agents/plugins/marketplace.json` |
| 看不到 skills | 检查当前项目 `.agents/skills/` 是否存在 RealAnalyst skills |
| 不知道下一步 | 让 LLM 读取 `https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/llm-next-steps.md` |
| 没有 `metadata/` | 这是预期行为；确认要保存抽取结果或执行分析后再按需创建 |
| 没有 `runtime/` | 重新运行安装器；如果使用了 `--skip-project-runtime`，则不会安装项目内 runtime support |
| 依赖安装失败 | 进入 `~/plugins/realanalyst` 后重新运行 `python3 -m pip install -r requirements.txt` |
| demo metadata 校验失败 | 运行 `python3 skills/metadata/scripts/metadata.py validate` 查看错误 |
| 不确定从哪里开始 | 在 Codex 输入 `/skill RA:getting-started` |
