from __future__ import annotations

import os
import sys
from pathlib import Path


def _has_skill_root(candidate: Path) -> bool:
    return (candidate / "skills").is_dir() or (candidate / ".agents" / "skills").is_dir()


def _find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in [start, *start.parents]:
        if _has_skill_root(candidate):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())


def bootstrap_workspace_path() -> Path:
    roots = [WORKSPACE_DIR]
    if (WORKSPACE_DIR / ".agents" / "skills").is_dir():
        roots.append(WORKSPACE_DIR / ".agents")
    for root in reversed(roots):
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
    return WORKSPACE_DIR


def ensure_workspace_on_path() -> Path:
    return bootstrap_workspace_path()
