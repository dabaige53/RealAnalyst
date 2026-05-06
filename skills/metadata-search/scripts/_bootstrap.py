from __future__ import annotations

import os
import sys
from pathlib import Path


def find_workspace(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    for candidate in (start, *start.parents):
        if (candidate / "skills").is_dir() and (candidate / "metadata").is_dir():
            return candidate
        if (candidate / ".agents" / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Cannot find RealAnalyst workspace from {start}")


def ensure_workspace_on_path() -> Path:
    workspace = find_workspace(Path(__file__).resolve())
    roots = [workspace]
    if (workspace / ".agents" / "skills").is_dir():
        roots.append(workspace / ".agents")
    for root in reversed(roots):
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
    return workspace


def bootstrap_workspace_path() -> Path:
    return ensure_workspace_on_path()
