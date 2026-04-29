# Install RealAnalyst for Codex

RealAnalyst 是 Codex plugin。默认安装为“当前项目启用”，不会在所有项目里自动启动。

## Enable In Current Project

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 -
```

这条命令会自动完成：

- clone / update `https://github.com/dabaige53/RealAnalyst`
- 安装到 `~/plugins/realanalyst`
- 创建 `.venv` 并安装 Python dependencies
- 写入当前项目的 `.agents/plugins/marketplace.json`
- 校验 `.codex-plugin/plugin.json`
- 校验 demo metadata

完成后重启 Codex，然后输入：

```text
/skill getting-started
```

## Enable In Another Project

在任意目录执行都可以指定目标项目：

```bash
curl -fsSL https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/scripts/install_codex_plugin.py | python3 - --project /path/to/your/project
```

这样 RealAnalyst 只会写入：

```text
/path/to/your/project/.agents/plugins/marketplace.json
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

## Use It

第一次使用：

```text
/skill getting-started
帮我初始化 RealAnalyst 项目，并告诉我第一步需要准备哪些信息。
```

维护 metadata：

```text
/skill metadata
帮我注册一个数据集，并维护字段、指标、筛选器和业务口径。
```

执行完整分析：

```text
/skill analysis-run
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
| Codex 看不到插件 | 重启 Codex，并检查 `~/.agents/plugins/marketplace.json` |
| 依赖安装失败 | 进入 `~/plugins/realanalyst` 后重新运行 `python3 -m pip install -r requirements.txt` |
| demo metadata 校验失败 | 运行 `python3 skills/metadata/scripts/metadata.py validate` 查看错误 |
| 不确定从哪里开始 | 在 Codex 输入 `/skill getting-started` |
