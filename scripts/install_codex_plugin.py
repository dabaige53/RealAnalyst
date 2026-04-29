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
PROJECT_DIRS = ("docs", "examples", "lib", "metadata", "runtime", "schemas", "scripts", "skills")
PROJECT_FILES = (".env.example", "INSTALL.md")
GITIGNORE_BLOCK = """# RealAnalyst local outputs
.env
.env.*
!.env.example
.venv/
*.duckdb
*.db
*.sqlite
*.sqlite3
jobs/
logs/
metadata/index/
metadata/osi/
runtime/**/*.db
runtime/**/*.sqlite
"""
NEXT_STEPS_TEMPLATE = """# RealAnalyst Next Steps

RealAnalyst has been installed for this project.

## 1. Restart Codex

Restart Codex so it can reload project-local plugins and skills.

## 2. Check Installed Files

The installer created or updated:

- `.agents/plugins/marketplace.json`
- `.agents/skills/`
- `metadata/`
- `runtime/`
- `examples/`
- `schemas/`
- `scripts/`
- `.env.example`

## 3. Start In Codex

Run:

```text
/skill getting-started
```

Then ask:

```text
帮我初始化 RealAnalyst 项目，并告诉我第一步需要准备哪些信息。
```

## 4. Run The Demo Check

From this project directory:

```bash
python3 examples/build_demo_duckdb.py
python3 runtime/duckdb/register_duckdb_sources.py
python3 skills/data-export/scripts/duckdb/run_tests.py
```

## 5. Connect Real Data When Ready

Copy `.env.example` to `.env` and fill Tableau credentials only when needed:

```text
TABLEAU_BASE_URL=
TABLEAU_SITE_ID=
TABLEAU_PAT_NAME=
TABLEAU_PAT_SECRET=
```

Do not commit `.env`, `jobs/`, local databases, or generated metadata indexes.
"""


def run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool = False) -> None:
    label = " ".join(cmd)
    print(f"$ {label}")
    if dry_run:
        return
    subprocess.run(cmd, cwd=cwd, check=True)


def copy_file(source: Path, target: Path, *, force: bool, dry_run: bool) -> str:
    if target.exists() and not force:
        return "skipped"
    print(f"$ copy {source} -> {target}")
    if dry_run:
        return "created"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return "created"


def copy_tree_contents(source: Path, target: Path, *, force: bool, dry_run: bool) -> tuple[int, int]:
    created = 0
    skipped = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        status = copy_file(path, target / rel, force=force, dry_run=dry_run)
        if status == "created":
            created += 1
        else:
            skipped += 1
    return created, skipped


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


def install_project_files(plugin_dir: Path, project_dir: Path, *, force: bool, dry_run: bool) -> None:
    print(f"$ initialize RealAnalyst workspace files in {project_dir}")
    project_dir.mkdir(parents=True, exist_ok=True)

    for rel in PROJECT_FILES:
        source = plugin_dir / rel
        if source.exists():
            copy_file(source, project_dir / rel, force=force, dry_run=dry_run)

    for rel in PROJECT_DIRS:
        source = plugin_dir / rel
        if source.is_dir():
            created, skipped = copy_tree_contents(source, project_dir / rel, force=force, dry_run=dry_run)
            print(f"  {rel}/: {created} installed, {skipped} kept")


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


def update_gitignore(project_dir: Path, *, dry_run: bool) -> None:
    path = project_dir / ".gitignore"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if "# RealAnalyst local outputs" in current:
        return
    print(f"$ update {path}")
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if not current or current.endswith("\n") else "\n"
    path.write_text(f"{current}{prefix}\n{GITIGNORE_BLOCK}", encoding="utf-8")


def write_next_steps(project_dir: Path, *, dry_run: bool) -> None:
    path = project_dir / "REALANALYST_NEXT_STEPS.md"
    print(f"$ write {path}")
    if dry_run:
        return
    path.write_text(NEXT_STEPS_TEMPLATE, encoding="utf-8")


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


def validate_install(plugin_dir: Path, project_dir: Path, *, dry_run: bool) -> None:
    venv_python = python_bin(plugin_dir / ".venv")
    py = venv_python if venv_python.exists() or dry_run else Path(sys.executable)
    run([str(py), "-m", "json.tool", ".codex-plugin/plugin.json"], cwd=plugin_dir, dry_run=dry_run)
    run([str(py), "skills/metadata/scripts/metadata.py", "validate"], cwd=plugin_dir, dry_run=dry_run)
    run([str(py), "skills/metadata/scripts/metadata.py", "--workspace", str(project_dir), "validate"], cwd=plugin_dir, dry_run=dry_run)


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
    parser.add_argument("--skip-project-files", action="store_true", help="Only register the plugin, do not copy skills/files into the project")
    parser.add_argument("--force", action="store_true", help="Overwrite existing RealAnalyst-installed project files")
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
    if not args.global_install and not args.skip_project_files:
        install_project_files(plugin_dir, project_dir, force=args.force, dry_run=args.dry_run)
        install_project_skills(plugin_dir, project_dir, force=args.force, dry_run=args.dry_run)
        update_gitignore(project_dir, dry_run=args.dry_run)
        write_next_steps(project_dir, dry_run=args.dry_run)
    validate_install(plugin_dir, project_dir, dry_run=args.dry_run)

    print("\nInstalled RealAnalyst for Codex.")
    print(f"Enabled marketplace: {marketplace}")
    if not args.global_install and not args.skip_project_files:
        print(f"Installed skills: {project_dir / '.agents' / 'skills'}")
        print(f"Initialized files: {project_dir}")
        print(f"Next steps: {project_dir / 'REALANALYST_NEXT_STEPS.md'}")
    print("Restart Codex, then run:")
    print("/skill getting-started")
    print("\nSuggested first prompt:")
    print("帮我初始化 RealAnalyst 项目，并告诉我第一步需要准备哪些信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
