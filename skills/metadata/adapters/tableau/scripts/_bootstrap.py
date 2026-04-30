from __future__ import annotations

import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def _has_skill_root(candidate: Path) -> bool:
    return (candidate / "skills").is_dir() or (candidate / ".agents" / "skills").is_dir()


def _find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    for candidate in [start, *start.parents]:
        if (candidate / "runtime").is_dir() and _has_skill_root(candidate):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


def _find_tableau_scripts_dir(workspace_dir: Path) -> Path:
    candidates = [
        workspace_dir / "skills" / "tableau" / "scripts",
        workspace_dir / ".agents" / "skills" / "tableau" / "scripts",
        workspace_dir / "skills" / "data-export" / "scripts" / "tableau",
        workspace_dir / ".agents" / "skills" / "data-export" / "scripts" / "tableau",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate tableau skill scripts from {workspace_dir}")


WORKSPACE_DIR = _find_workspace_root(SCRIPT_DIR)
TABLEAU_SCRIPTS_DIR = _find_tableau_scripts_dir(WORKSPACE_DIR)


def bootstrap_workspace_path() -> Path:
    roots = [WORKSPACE_DIR]
    if (WORKSPACE_DIR / ".agents" / "skills").is_dir():
        roots.append(WORKSPACE_DIR / ".agents")
    for root in reversed(roots):
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
    return WORKSPACE_DIR


def bootstrap_tableau_scripts_path() -> Path:
    if str(TABLEAU_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(TABLEAU_SCRIPTS_DIR))
    return TABLEAU_SCRIPTS_DIR
