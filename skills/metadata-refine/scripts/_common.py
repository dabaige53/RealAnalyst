from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def find_workspace(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "metadata").is_dir() and ((candidate / "skills").is_dir() or (candidate / ".agents" / "skills").is_dir()):
            return candidate
        if (candidate / ".agents" / "skills").is_dir():
            return candidate
    return Path(__file__).resolve().parents[3]


DEFAULT_WORKSPACE = find_workspace(Path(__file__).resolve())


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def workspace_path(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return DEFAULT_WORKSPACE


def make_refine_id(job_id: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    suffix = sanitize_token(job_id or "refine")
    return f"refine-{stamp}-{suffix}"


def sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return token.strip("-")[:80] or "refine"


def job_dir(workspace: Path, session_id: str) -> Path:
    return workspace / "jobs" / session_id


def meta_dir(workspace: Path, session_id: str) -> Path:
    return job_dir(workspace, session_id) / ".meta"


def feedback_path(workspace: Path, session_id: str) -> Path:
    return meta_dir(workspace, session_id) / "metadata_feedback.jsonl"


def runtime_refine_dir(workspace: Path, refine_id: str) -> Path:
    return workspace / "runtime" / "metadata-refine" / refine_id


def source_refine_dir(workspace: Path, refine_id: str) -> Path:
    return workspace / "metadata" / "sources" / "refine" / refine_id


def relpath(workspace: Path, path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        return str(p)
    try:
        return str(p.relative_to(workspace))
    except ValueError:
        return str(p)


def resolve_workspace_path(workspace: Path, path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (workspace / p).resolve()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def upsert_job_artifact(workspace: Path, session_id: str, item: dict[str, Any]) -> None:
    index_path = meta_dir(workspace, session_id) / "artifact_index.json"
    payload = read_json(index_path)
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    item = dict(item)
    item.setdefault("created_at", now_iso())
    if item.get("path"):
        item["path"] = relpath(workspace, str(item["path"]))
    path_key = str(item.get("path") or "")
    replaced = False
    for idx, existing in enumerate(items):
        if isinstance(existing, dict) and str(existing.get("path") or "") == path_key:
            merged = dict(existing)
            merged.update(item)
            items[idx] = merged
            replaced = True
            break
    if not replaced:
        items.append(item)
    payload.setdefault("version", 1)
    payload.setdefault("job_id", session_id)
    payload.setdefault("created_at", now_iso())
    payload["updated_at"] = now_iso()
    payload["items"] = items
    write_json(index_path, payload)
