#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_NAME = "realanalyst"
REPO_URL = "https://github.com/dabaige53/RealAnalyst.git"
NEXT_STEPS_FILENAME = "realanalyst-next-steps.md"


def next_steps_text(project_dir: Path, plugin_dir: Path, *, skills_installed: bool) -> str:
    skills_status = "已安装到 `.agents/skills/`" if skills_installed else "本次未安装项目内 skills"
    env_path = plugin_dir / ".env"
    return f"""# RealAnalyst 安装后的 LLM 引导

你正在帮助用户在当前项目里使用 RealAnalyst。安装已经完成，但项目仍然是干净的：不要因为插件安装完成就主动创建业务工作区。

## 先对用户这样说

可以直接告诉用户：

```text
RealAnalyst 已经装好，并且只在当前项目启用。当前项目仍然保持干净，所以没有创建 metadata、runtime、jobs、logs，也没有写入 demo。下一步我们先确认你要接入哪类数据源，再决定是否需要保存抽取结果。
```

然后给用户三个选择，不要替用户擅自选：

1. **我已经有 Tableau 报表 / workbook**：先准备 Tableau 连接信息和目标 workbook。
2. **我有 DuckDB / 数据库 / CSV 文件**：先准备文件路径、表名、字段说明。
3. **我还不确定数据源**：先用 `/skill getting-started` 梳理要抽取哪些元数据。

## 本次安装写入了什么

- 插件注册：`.agents/plugins/marketplace.json`
- 项目内 skills：{skills_status}
- 这份给 LLM 读取的引导：`.agents/plugins/{NEXT_STEPS_FILENAME}`

## 不要做什么

- Do not create `metadata/`, `runtime/`, `jobs/`, `logs/`, project `.env`, or `.gitignore` during installation checks.
- Do not ask the user to paste secrets into a public document or commit them.
- Do not add demo data unless the user explicitly asks for a demo.
- Do not modify user business files just because the plugin was installed.
- Only create RealAnalyst workspace folders after the user confirms they want to initialize or use a skill that needs them.

## 第一步怎么继续

如果用户想直接开始，建议让用户重启 Codex，然后输入：

```text
/skill getting-started
```

更自然的第一句应该聚焦“抽取元数据”：

```text
我已经装好了 RealAnalyst。请先帮我确认数据源类型，并告诉我应该准备哪些信息来抽取字段、指标、筛选器和业务口径。
```

第一步应该是确认数据源和抽取范围。只有用户确认要把抽取结果保存到项目里时，才创建 `metadata/` 并写入整理后的 YAML。

```text
/skill getting-started
帮我确认数据源类型，并列出抽取元数据前需要准备的信息。
```

## 如果用户要接 Tableau

不要让用户把密钥写进 README、聊天记录或仓库文件。引导用户把本机私密配置写到插件安装目录的 `.env`：

```text
{env_path}
```

需要填写：

```text
TABLEAU_BASE_URL=https://your-tableau-server
TABLEAU_SITE_ID=your-site-id
TABLEAU_PAT_NAME=your-personal-access-token-name
TABLEAU_PAT_SECRET=your-personal-access-token-secret
```

说明口径：

- `TABLEAU_BASE_URL`：Tableau Server / Cloud 的根地址。
- `TABLEAU_SITE_ID`：站点 ID；默认站点通常可以留空，但要让用户确认。
- `TABLEAU_PAT_NAME`：用户在 Tableau 创建的 Personal Access Token 名称。
- `TABLEAU_PAT_SECRET`：Personal Access Token secret，只放本机 `.env`，不要提交。

填完后，再让用户说出要同步的 workbook / view / dashboard 名称。不要一上来全量扫描。

## 如果用户要接 DuckDB / 文件数据

先问这些信息：

- 数据文件或 DuckDB 路径在哪里。
- 要分析的表、视图或 CSV/Excel sheet 是哪个。
- 关键日期字段、金额字段、维度字段分别是什么。
- 哪些指标口径必须先确认。
- 用户是否同意在抽取完成后把结果保存为项目内 metadata 文件。

## Skills 快速入口

把下面这些入口教给用户。用户不需要记目录，只需要说目标：

### 先开始

```text
/skill getting-started
帮我确认数据源类型，并列出抽取元数据前需要准备的信息。
```

### 整理元数据

```text
/skill metadata
我有一个数据源需要整理 metadata。请先问我要来源、字段、指标、筛选器和证据，不要直接创建文件。
```

### 整理指标口径

```text
/skill metadata
帮我整理这些指标的业务口径：指标名称、计算公式、单位、粒度、适用范围、证据和待确认问题。
```

### 整理术语表

```text
/skill metadata
帮我把这些业务术语整理成 glossary，包含中文名、英文名、同义词、定义、来源证据和是否需要 review。
```

### 从 Tableau 抽取 metadata

```text
/skill metadata
我要从 Tableau workbook 抽取字段、筛选器、参数和指标口径。请先检查 .env 需要哪些信息，再问我要 workbook/view/dashboard 名称。
```

### 从 DuckDB / CSV / Excel 抽取 metadata

```text
/skill metadata
我要从本地 DuckDB/CSV/Excel 抽取字段和指标口径。请先问我要文件路径、表名或 sheet 名、关键字段和分析目标。
```

### 生成分析计划

```text
/skill analysis-plan
基于已经整理好的 metadata，帮我生成分析计划。先列出需要确认的数据源、指标、维度、筛选条件和风险。
```

### 执行完整分析

```text
/skill analysis-run
基于已确认的 metadata 和分析计划，帮我执行取数、画像、分析和报告。每一步都保留证据和产物路径。
```

## 安装检查

- Confirm `.agents/plugins/marketplace.json` contains `realanalyst`.
- Confirm `.agents/skills/getting-started/SKILL.md` exists.
- Confirm `.agents/skills/metadata/SKILL.md` exists.
- Confirm these folders were not created by install: `metadata/`, `runtime/`, `jobs/`, `logs/`.

## 当前路径

```text
Project: {project_dir}
Plugin: {plugin_dir}
Env: {env_path}
```

## 给用户的下一句

如果用户没有明确目标，直接问：

```text
你现在是想从 Tableau、DuckDB、CSV/Excel 里抽取元数据，还是先手工整理字段和指标口径？我会先确认数据源和范围，再决定是否需要写入项目文件。
```
"""


def run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool = False) -> None:
    label = " ".join(cmd)
    print(f"$ {label}", flush=True)
    if dry_run:
        return
    subprocess.run(cmd, cwd=cwd, check=True)


def python_bin(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def clone_or_update(repo_url: str, target_dir: Path, *, dry_run: bool) -> None:
    if target_dir.exists():
        if not (target_dir / ".git").exists():
            raise SystemExit(f"Target exists but is not a git repo: {target_dir}")
        run(["git", "pull", "--ff-only"], cwd=target_dir, dry_run=dry_run)
        return
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", repo_url, str(target_dir)], dry_run=dry_run)


def install_dependencies(plugin_dir: Path, *, dry_run: bool) -> None:
    venv_dir = plugin_dir / ".venv"
    run([sys.executable, "-m", "venv", str(venv_dir)], dry_run=dry_run)
    py = python_bin(venv_dir)
    run([str(py), "-m", "pip", "install", "-U", "pip"], dry_run=dry_run)
    run([str(py), "-m", "pip", "install", "-r", "requirements.txt"], cwd=plugin_dir, dry_run=dry_run)


def ensure_plugin_env(plugin_dir: Path, *, dry_run: bool) -> Path:
    env_path = plugin_dir / ".env"
    if env_path.exists():
        print(f"$ keep existing {env_path}", flush=True)
        return env_path

    source = plugin_dir / ".env.example"
    print(f"$ initialize {env_path}", flush=True)
    if dry_run:
        return env_path
    if source.exists():
        shutil.copy2(source, env_path)
    else:
        env_path.write_text(
            "TABLEAU_BASE_URL=\nTABLEAU_SITE_ID=\nTABLEAU_PAT_NAME=\nTABLEAU_PAT_SECRET=\n",
            encoding="utf-8",
        )
    return env_path


def install_project_skills(plugin_dir: Path, project_dir: Path, *, force: bool, dry_run: bool) -> None:
    skills_source = plugin_dir / "skills"
    skills_target = project_dir / ".agents" / "skills"
    print(f"$ install project-local skills into {skills_target}")
    for source in sorted(path for path in skills_source.iterdir() if path.is_dir() and (path / "SKILL.md").exists()):
        target = skills_target / source.name
        marker = target / ".realanalyst-installed"
        if target.exists() and not marker.exists() and not force:
            print(f"  skip {target} (already exists; use --force to overwrite)")
            continue
        if target.exists() and (force or marker.exists()):
            print(f"$ replace {target}")
            if not dry_run:
                shutil.rmtree(target)
        if dry_run:
            print(f"$ copytree {source} -> {target}")
            continue
        shutil.copytree(source, target)
        marker.write_text("installed by RealAnalyst\n", encoding="utf-8")


def load_marketplace(path: Path, *, name: str) -> dict:
    if not path.exists():
        return {"name": name, "interface": {"displayName": name}, "plugins": []}
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_marketplace(path: Path, plugin_dir: Path, *, name: str, dry_run: bool) -> None:
    data = load_marketplace(path, name=name)
    data.setdefault("name", name)
    data.setdefault("interface", {"displayName": name})
    plugins = data.setdefault("plugins", [])
    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": str(plugin_dir)},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }

    for index, item in enumerate(plugins):
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME:
            plugins[index] = entry
            break
    else:
        plugins.append(entry)

    print(f"$ update {path}")
    if dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_next_steps(path: Path, project_dir: Path, plugin_dir: Path, *, skills_installed: bool, dry_run: bool) -> None:
    print(f"$ write {path}", flush=True)
    if dry_run:
        print(next_steps_text(project_dir, plugin_dir, skills_installed=skills_installed))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(next_steps_text(project_dir, plugin_dir, skills_installed=skills_installed), encoding="utf-8")


def validate_install(plugin_dir: Path, *, dry_run: bool) -> None:
    venv_python = python_bin(plugin_dir / ".venv")
    py = venv_python if venv_python.exists() or dry_run else Path(sys.executable)
    run([str(py), "-m", "json.tool", ".codex-plugin/plugin.json"], cwd=plugin_dir, dry_run=dry_run)
    run([str(py), "skills/metadata/scripts/metadata.py", "validate"], cwd=plugin_dir, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install RealAnalyst as a local Codex plugin.")
    parser.add_argument("--repo", default=REPO_URL, help="Git repository URL")
    parser.add_argument("--plugin-dir", default=str(Path.home() / "plugins" / PLUGIN_NAME), help="Plugin install directory")
    parser.add_argument(
        "--project",
        default=".",
        help="Project directory where RealAnalyst should be enabled. Defaults to current directory.",
    )
    parser.add_argument("--global", dest="global_install", action="store_true", help="Enable for all Codex projects")
    parser.add_argument("--marketplace", default="", help="Override marketplace.json path")
    parser.add_argument("--skip-deps", action="store_true", help="Skip Python dependency installation")
    parser.add_argument(
        "--skip-project-skills",
        "--skip-project-files",
        dest="skip_project_skills",
        action="store_true",
        help="Only register the plugin, do not install project-local skills",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing RealAnalyst-installed project skills")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files")
    args = parser.parse_args()

    plugin_dir = Path(args.plugin_dir).expanduser().resolve()
    project_dir = Path(args.project).expanduser().resolve()
    if args.marketplace:
        marketplace = Path(args.marketplace).expanduser().resolve()
        marketplace_name = "local-plugins"
    elif args.global_install:
        marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
        marketplace_name = "global-plugins"
    else:
        marketplace = project_dir / ".agents" / "plugins" / "marketplace.json"
        marketplace_name = f"{project_dir.name}-plugins"

    clone_or_update(args.repo, plugin_dir, dry_run=args.dry_run)
    if not args.skip_deps:
        install_dependencies(plugin_dir, dry_run=args.dry_run)
    env_path = ensure_plugin_env(plugin_dir, dry_run=args.dry_run)
    upsert_marketplace(marketplace, plugin_dir, name=marketplace_name, dry_run=args.dry_run)
    if not args.global_install and not args.skip_project_skills:
        install_project_skills(plugin_dir, project_dir, force=args.force, dry_run=args.dry_run)
    next_steps_path = marketplace.parent / NEXT_STEPS_FILENAME
    write_next_steps(
        next_steps_path,
        project_dir,
        plugin_dir,
        skills_installed=not args.global_install and not args.skip_project_skills,
        dry_run=args.dry_run,
    )
    validate_install(plugin_dir, dry_run=args.dry_run)

    print("\nInstalled RealAnalyst for Codex.")
    print(f"Enabled marketplace: {marketplace}")
    print(f"Plugin env file: {env_path}")
    print(f"LLM next-step guide: {next_steps_path}")
    if not args.global_install and not args.skip_project_skills:
        print(f"Installed skills: {project_dir / '.agents' / 'skills'}")
        print("No workspace folders or user project files were created.")
    print("Restart Codex, then run:")
    print("/skill getting-started")
    print("\nSuggested first prompt:")
    print("帮我确认数据源类型，并列出抽取元数据前需要准备的信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
