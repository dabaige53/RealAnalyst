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


WORKSPACE_DIR = _find_workspace_root(SCRIPT_DIR)


def bootstrap_workspace_path() -> Path:
    if str(WORKSPACE_DIR) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_DIR))
    return WORKSPACE_DIR
