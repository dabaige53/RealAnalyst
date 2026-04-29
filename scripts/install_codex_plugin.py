#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PLUGIN_NAME = "realanalyst"
REPO_URL = "https://github.com/dabaige53/RealAnalyst.git"


def run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool = False) -> None:
    label = " ".join(cmd)
    print(f"$ {label}")
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


def validate_install(plugin_dir: Path, *, dry_run: bool) -> None:
    py = python_bin(plugin_dir / ".venv")
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
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files")
    args = parser.parse_args()

    plugin_dir = Path(args.plugin_dir).expanduser().resolve()
    if args.marketplace:
        marketplace = Path(args.marketplace).expanduser().resolve()
        marketplace_name = "local-plugins"
    elif args.global_install:
        marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
        marketplace_name = "global-plugins"
    else:
        project_dir = Path(args.project).expanduser().resolve()
        marketplace = project_dir / ".agents" / "plugins" / "marketplace.json"
        marketplace_name = f"{project_dir.name}-plugins"

    clone_or_update(args.repo, plugin_dir, dry_run=args.dry_run)
    if not args.skip_deps:
        install_dependencies(plugin_dir, dry_run=args.dry_run)
    upsert_marketplace(marketplace, plugin_dir, name=marketplace_name, dry_run=args.dry_run)
    validate_install(plugin_dir, dry_run=args.dry_run)

    print("\nInstalled RealAnalyst for Codex.")
    print(f"Enabled marketplace: {marketplace}")
    print("Restart Codex, then run:")
    print("/skill getting-started")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
