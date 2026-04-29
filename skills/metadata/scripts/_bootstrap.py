from __future__ import annotations

import sys
from pathlib import Path


def find_workspace(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "skills").is_dir() and (candidate / "metadata").is_dir():
            return candidate
    raise RuntimeError(f"Cannot find RealAnalyst workspace from {start}")


def ensure_workspace_on_path() -> Path:
    workspace = find_workspace(Path(__file__).resolve())
    workspace_text = str(workspace)
    if workspace_text not in sys.path:
        sys.path.insert(0, workspace_text)
    return workspace


def bootstrap_workspace_path() -> Path:
    return ensure_workspace_on_path()
