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


def next_steps_text(project_dir: Path, *, skills_installed: bool) -> str:
    skills_status = "installed" if skills_installed else "not installed by this run"
    return f"""# RealAnalyst Next Steps For LLM

RealAnalyst has been enabled for this Codex project.

## What Was Installed

- Plugin registry: `.agents/plugins/marketplace.json`
- Project-local skills: `.agents/skills/` ({skills_status})
- This guide: `.agents/plugins/{NEXT_STEPS_FILENAME}`

## Guardrails

- Do not create `metadata/`, `runtime/`, `jobs/`, `logs/`, `.env`, or `.gitignore` during installation checks.
- Do not add demo data unless the user explicitly asks for a demo.
- Do not modify user business files just because the plugin was installed.
- Only create RealAnalyst workspace folders when the user explicitly asks to initialize or use a skill that needs them.

## After Install

Tell the user:

1. Restart Codex so project-local plugins and skills reload.
2. Start with `/skill getting-started`.
3. If they want to initialize a RealAnalyst workspace, ask for confirmation first.

Suggested prompt:

```text
/skill getting-started
帮我初始化 RealAnalyst 项目，并告诉我第一步需要准备哪些信息。
```

## Validation Checklist

- Confirm `.agents/plugins/marketplace.json` contains `realanalyst`.
- Confirm `.agents/skills/getting-started/SKILL.md` exists.
- Confirm `.agents/skills/metadata/SKILL.md` exists.
- Confirm these folders were not created by install: `metadata/`, `runtime/`, `jobs/`, `logs/`.

Project path:

```text
{project_dir}
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


def write_next_steps(path: Path, project_dir: Path, *, skills_installed: bool, dry_run: bool) -> None:
    print(f"$ write {path}", flush=True)
    if dry_run:
        print(next_steps_text(project_dir, skills_installed=skills_installed))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(next_steps_text(project_dir, skills_installed=skills_installed), encoding="utf-8")


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
    upsert_marketplace(marketplace, plugin_dir, name=marketplace_name, dry_run=args.dry_run)
    if not args.global_install and not args.skip_project_skills:
        install_project_skills(plugin_dir, project_dir, force=args.force, dry_run=args.dry_run)
    next_steps_path = marketplace.parent / NEXT_STEPS_FILENAME
    write_next_steps(
        next_steps_path,
        project_dir,
        skills_installed=not args.global_install and not args.skip_project_skills,
        dry_run=args.dry_run,
    )
    validate_install(plugin_dir, dry_run=args.dry_run)

    print("\nInstalled RealAnalyst for Codex.")
    print(f"Enabled marketplace: {marketplace}")
    print(f"LLM next-step guide: {next_steps_path}")
    if not args.global_install and not args.skip_project_skills:
        print(f"Installed skills: {project_dir / '.agents' / 'skills'}")
        print("No workspace folders or user project files were created.")
    print("Restart Codex, then run:")
    print("/skill getting-started")
    print("\nSuggested first prompt:")
    print("帮我初始化 RealAnalyst 项目，并告诉我第一步需要准备哪些信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
