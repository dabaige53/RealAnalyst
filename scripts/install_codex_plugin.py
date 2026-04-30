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
GUIDE_URL = "https://raw.githubusercontent.com/dabaige53/RealAnalyst/main/docs/llm-next-steps.md"
DEFAULT_VERSION = "latest"
INSTALL_CONFIG = ".realanalyst-install.json"


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


def normalize_version(value: str | None) -> str:
    raw = (value or DEFAULT_VERSION).strip()
    if not raw or raw == DEFAULT_VERSION:
        return DEFAULT_VERSION
    return raw if raw.startswith("v") else f"v{raw}"


def install_config_path(plugin_dir: Path) -> Path:
    return plugin_dir / INSTALL_CONFIG


def read_install_config(plugin_dir: Path) -> dict:
    path = install_config_path(plugin_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_version(plugin_dir: Path, requested: str | None) -> str:
    if requested is not None:
        return normalize_version(requested)
    return normalize_version(read_install_config(plugin_dir).get("version"))


def write_install_config(plugin_dir: Path, *, repo_url: str, version: str, dry_run: bool) -> None:
    path = install_config_path(plugin_dir)
    payload = {"repo": repo_url, "version": version}
    print(f"$ write {path}")
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checkout_version(target_dir: Path, *, version: str, dry_run: bool) -> None:
    if version == DEFAULT_VERSION:
        run(["git", "switch", "main"], cwd=target_dir, dry_run=dry_run)
        run(["git", "pull", "--ff-only", "origin", "main"], cwd=target_dir, dry_run=dry_run)
        return
    run(["git", "checkout", "--detach", f"refs/tags/{version}"], cwd=target_dir, dry_run=dry_run)


def clone_or_update(repo_url: str, target_dir: Path, *, version: str, dry_run: bool) -> None:
    if target_dir.exists():
        if not (target_dir / ".git").exists():
            raise SystemExit(f"Target exists but is not a git repo: {target_dir}")
        run(["git", "fetch", "origin", "--tags", "--prune"], cwd=target_dir, dry_run=dry_run)
        checkout_version(target_dir, version=version, dry_run=dry_run)
        return
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", repo_url, str(target_dir)], dry_run=dry_run)
    if version != DEFAULT_VERSION:
        run(["git", "fetch", "origin", "--tags", "--prune"], cwd=target_dir, dry_run=dry_run)
        checkout_version(target_dir, version=version, dry_run=dry_run)


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


def install_project_runtime(plugin_dir: Path, project_dir: Path, *, dry_run: bool) -> None:
    runtime_source = plugin_dir / "runtime"
    runtime_target = project_dir / "runtime"
    print(f"$ install project-local runtime into {runtime_target}")
    if dry_run:
        print(f"$ copytree {runtime_source} -> {runtime_target} (ignore registry db/cache files)")
        return
    shutil.copytree(
        runtime_source,
        runtime_target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("*.db", "*.db-*", "__pycache__", "*.pyc"),
    )


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
    venv_python = python_bin(plugin_dir / ".venv")
    py = venv_python if venv_python.exists() or dry_run else Path(sys.executable)
    run([str(py), "-m", "json.tool", ".codex-plugin/plugin.json"], cwd=plugin_dir, dry_run=dry_run)
    run([str(py), "skills/metadata/scripts/metadata.py", "validate"], cwd=plugin_dir, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install RealAnalyst as a local Codex plugin.")
    parser.add_argument("--repo", default=REPO_URL, help="Git repository URL")
    parser.add_argument("--plugin-dir", default=str(Path.home() / "plugins" / PLUGIN_NAME), help="Plugin install directory")
    parser.add_argument(
        "--version",
        default=None,
        help="Install strategy: latest for main auto-update, or a fixed release tag such as 0.2.6 / v0.2.6. Defaults to prior install config, then latest.",
    )
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
    parser.add_argument("--skip-project-runtime", action="store_true", help="Do not install project-local runtime support files")
    parser.add_argument("--force", action="store_true", help="Overwrite existing RealAnalyst-installed project skills")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files")
    args = parser.parse_args()

    plugin_dir = Path(args.plugin_dir).expanduser().resolve()
    version = resolve_version(plugin_dir, args.version)
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

    clone_or_update(args.repo, plugin_dir, version=version, dry_run=args.dry_run)
    write_install_config(plugin_dir, repo_url=args.repo, version=version, dry_run=args.dry_run)
    if not args.skip_deps:
        install_dependencies(plugin_dir, dry_run=args.dry_run)
    env_path = ensure_plugin_env(plugin_dir, dry_run=args.dry_run)
    upsert_marketplace(marketplace, plugin_dir, name=marketplace_name, dry_run=args.dry_run)
    if not args.global_install and not args.skip_project_skills:
        install_project_skills(plugin_dir, project_dir, force=args.force, dry_run=args.dry_run)
    if not args.global_install and not args.skip_project_runtime:
        install_project_runtime(plugin_dir, project_dir, dry_run=args.dry_run)
    validate_install(plugin_dir, dry_run=args.dry_run)

    print("\nInstalled RealAnalyst for Codex.")
    print(f"Version strategy: {version}")
    print(f"Enabled marketplace: {marketplace}")
    print(f"Plugin env file: {env_path}")
    print(f"Online LLM guide: {GUIDE_URL}")
    if not args.global_install and not args.skip_project_skills:
        print(f"Installed skills: {project_dir / '.agents' / 'skills'}")
    if not args.global_install and not args.skip_project_runtime:
        print(f"Installed runtime support: {project_dir / 'runtime'}")
        print("No jobs/logs/business workspace folders were created.")
    print("Restart Codex, then run:")
    print("/skill RA:getting-started")
    print("\nSuggested first prompt:")
    print("帮我确认数据源类型，并列出抽取元数据前需要准备的信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
