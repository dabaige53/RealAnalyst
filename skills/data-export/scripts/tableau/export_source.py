#!/usr/bin/env python3
# mypy: disable-error-code=import-untyped
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import pandas as pd

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import db_path, ensure_store_ready, load_registry_document
from runtime.tableau.source_context import build_source_context, write_source_context_bundle


def _workspace_dir() -> Path:
    return WORKSPACE_DIR


def _repo_root() -> Path:
    return _workspace_dir()


def _registry_path() -> Path:
    ensure_store_ready()
    return db_path()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _load_registry() -> dict[str, Any]:
    ensure_store_ready()
    data = load_registry_document()
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError("registry.db 格式错误：缺少 entries")
    return data


def _is_active_entry(entry: dict[str, Any]) -> bool:
    return str(entry.get("status") or "active").lower() == "active"


def _get_entry_by_source_id(registry: dict[str, Any], *, source_id: str) -> dict[str, Any] | None:
    for entry in registry.get("entries", []) or []:
        if isinstance(entry, dict) and entry.get("source_id") == source_id and _is_active_entry(entry):
            return entry
    return None


def _get_any_entry_by_source_id(registry: dict[str, Any], *, source_id: str) -> dict[str, Any] | None:
    for entry in registry.get("entries", []) or []:
        if isinstance(entry, dict) and entry.get("source_id") == source_id:
            return entry
    return None


def _available_source_ids(registry: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []
    for entry in registry.get("entries", []) or []:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("source_id"), str)
            and _is_active_entry(entry)
        ):
            source_ids.append(entry["source_id"])
    return source_ids


def _parse_views_arg(views: str | None) -> list[str]:
    if not views:
        return []
    parts = [p.strip() for p in views.split(",")]
    view_ids = [p for p in parts if p]
    seen: set[str] = set()
    deduped: list[str] = []
    for view_id in view_ids:
        if view_id in seen:
            raise ValueError(f"--views 包含重复 view_id：{view_id}")
        seen.add(view_id)
        deduped.append(view_id)
    return deduped


def _selected_domain_views(entry: dict[str, Any], *, view_ids: list[str]) -> list[dict[str, Any]]:
    views = entry.get("views") or []
    if not isinstance(views, list):
        raise ValueError("registry domain 配置错误：views 必须是 list")

    by_id: dict[str, dict[str, Any]] = {}
    for view in views:
        if not isinstance(view, dict):
            continue
        view_id = view.get("view_id")
        if isinstance(view_id, str) and view_id:
            by_id[view_id] = view

    selected: list[dict[str, Any]] = []
    for view_id in view_ids:
        view = by_id.get(view_id)
        if not view:
            raise ValueError(f"未在 registry 找到 domain view id：{view_id}")
        selected.append(view)
    return selected


def _source_alias(entry: dict[str, Any]) -> str:
    key = entry.get("key")
    return key if isinstance(key, str) else ""


def _view_alias(view: dict[str, Any]) -> str:
    key = view.get("key")
    return key if isinstance(key, str) else ""


def _output_name_for_source(*, source_id: str) -> str:
    return source_id


def _output_name_for_view(*, source_id: str, view_id: str) -> str:
    prefix = f"{source_id}."
    view_suffix = view_id[len(prefix) :] if view_id.startswith(prefix) else view_id
    return f"{source_id}.{view_suffix}"


_SAFE_FILENAME_RE = re.compile(r"[^0-9A-Za-z.\u4e00-\u9fff_-]+")


def _safe_filename(token: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", token).strip("._-")
    return cleaned or "unnamed"


def _resolve_output_dir(output_dir: str | None, session_id: str | None) -> Path:
    """Resolve output dir.

    Precedence:
      1) --output-dir
      2) --session-id
      3) env SESSION_ID

    Default contract path is: {baseDir}/jobs/{SESSION_ID}/
    """

    if output_dir:
        return Path(output_dir).expanduser().resolve()

    sid = (session_id or os.environ.get("SESSION_ID", "")).strip()
    if not sid:
        raise ValueError("SESSION_ID_REQUIRED")

    workspace_dir = _workspace_dir()
    jobs_dir = (workspace_dir / "jobs" / sid).resolve()
    return jobs_dir


def _export_budget_path(output_dir: Path) -> Path:
    return output_dir / "export_budget.json"


def _init_export_budget() -> dict[str, Any]:
    return {"max_count": 5, "used_count": 0, "history": []}


def _load_export_budget(path: Path) -> dict[str, Any]:
    if not path.exists():
        budget = _init_export_budget()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(budget, ensure_ascii=False, indent=2), encoding="utf-8")
        return budget

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    max_count = data.get("max_count", 5)
    used_count = data.get("used_count", 0)
    history = data.get("history", [])

    try:
        max_count = int(max_count)
    except (TypeError, ValueError):
        max_count = 5

    try:
        used_count = int(used_count)
    except (TypeError, ValueError):
        used_count = 0

    if not isinstance(history, list):
        history = []

    normalized = {"max_count": max_count, "used_count": used_count, "history": history}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def _record_export_budget(
    path: Path,
    budget: dict[str, Any],
    *,
    success: bool,
    source_id: str,
    view_id: str | None,
    view_luid: str | None,
) -> dict[str, Any]:
    used_count = budget.get("used_count", 0)
    try:
        used_count = int(used_count)
    except (TypeError, ValueError):
        used_count = 0

    max_count = budget.get("max_count", 5)
    try:
        max_count = int(max_count)
    except (TypeError, ValueError):
        max_count = 5

    history = budget.get("history", [])
    if not isinstance(history, list):
        history = []

    history.append(
        {
            "timestamp": _now_iso(),
            "source_id": source_id,
            "view_id": view_id,
            "view_luid": view_luid,
            "success": bool(success),
        }
    )

    # 预算只统计成功导出
    new_used_count = used_count + 1 if success else used_count

    updated = {"max_count": max_count, "used_count": new_used_count, "history": history}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


def _ensure_export_budget(
    *,
    output_dir: Path,
    source_id: str,
    required_success_quota: int,
) -> tuple[bool, dict[str, Any]]:
    """Budget gate.

    - Only counts successful exports.
    - For domain export, caller may require multiple view exports.

    Returns: (allowed, budget)
    """

    budget_path = _export_budget_path(output_dir)
    budget = _load_export_budget(budget_path)

    max_count = int(budget.get("max_count", 5) or 5)
    used_count = int(budget.get("used_count", 0) or 0)
    remaining = max(0, max_count - used_count)

    if remaining < required_success_quota:
        budget["remaining"] = remaining
        budget["required_success_quota"] = required_success_quota
        return False, budget

    budget["remaining"] = remaining
    budget["required_success_quota"] = required_success_quota
    return True, budget


def _is_long_table_csv(path: Path) -> bool:
    cols = pd.read_csv(path, nrows=0).columns
    return "度量名称" in cols and "度量值" in cols


def _final_wide_path(output_dir: Path, output_name: str) -> Path:
    return output_dir / "data" / f"交叉_{output_name}.csv"


def _resolve_output_artifact_path(output_dir: Path, path_value: str) -> Path | None:
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = output_dir / candidate

    resolved_output_dir = output_dir.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate != resolved_output_dir and resolved_output_dir not in resolved_candidate.parents:
        return None
    return resolved_candidate


def _output_name_collision_exists(output_dir: Path, output_name: str) -> bool:
    summary_path = output_dir / "export_summary.json"
    if not summary_path.exists():
        return False
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(payload, dict):
        return False

    target_paths = {
        str(_final_wide_path(output_dir, output_name).relative_to(output_dir)),
        f"profile/manifest_{_safe_filename(output_name)}.json",
        f"profile/assertions_{_safe_filename(output_name)}.json",
    }
    views = payload.get("views")
    if not isinstance(views, list):
        return False
    for view in views:
        if not isinstance(view, dict):
            continue
        for key in ("file_path", "manifest_path", "assertions_path"):
            value = view.get(key)
            if isinstance(value, str) and value in target_paths:
                return True
    return False


def _params_signature(vf_filters: list[str] | None, vp_filters: list[str] | None) -> str:
    payload = {"vf": vf_filters or [], "vp": vp_filters or []}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:8]


def _allocate_unique_output_name(
    *,
    output_dir: Path,
    base_output_name: str,
    vf_filters: list[str] | None,
    vp_filters: list[str] | None,
) -> str:
    if not _output_name_collision_exists(output_dir, base_output_name):
        return base_output_name

    signature = _params_signature(vf_filters, vp_filters)
    candidate = f"{base_output_name}__{signature}"
    if not _output_name_collision_exists(output_dir, candidate):
        return candidate

    for index in range(2, 50):
        candidate = f"{base_output_name}__{signature}__{index}"
        if not _output_name_collision_exists(output_dir, candidate):
            return candidate

    return f"{base_output_name}__{signature}__{int(datetime.now(timezone.utc).timestamp())}"


def _cleanup_failed_export_artifacts(
    *, output_dir: Path, output_name: str, result: dict[str, Any] | None = None
) -> None:
    candidate_paths: list[Path] = [
        output_dir / "data" / f"{output_name}.csv",
        _final_wide_path(output_dir, output_name),
        output_dir / "profile" / f"manifest_{_safe_filename(output_name)}.json",
        output_dir / "profile" / f"assertions_{_safe_filename(output_name)}.json",
        output_dir / "profile" / "manifest.json",
        output_dir / "profile" / "assertions.json",
    ]

    if result:
        for key in ("csv_path", "pivot_path", "manifest_path", "assertions_path"):
            path_value = result.get(key)
            if not isinstance(path_value, str) or not path_value:
                continue
            resolved = _resolve_output_artifact_path(output_dir, path_value)
            if resolved is not None:
                candidate_paths.append(resolved)

    seen: set[Path] = set()
    for path in candidate_paths:
        if path in seen:
            continue
        seen.add(path)
        path.unlink(missing_ok=True)


def _convert_or_rename_to_wide(
    *, raw_path: Path, wide_path: Path, output_name: str
) -> tuple[bool, str | None]:
    wide_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if _is_long_table_csv(raw_path):
            from export import pivot_long_to_wide

            pivot_content, pivot_warning, _ = pivot_long_to_wide(
                raw_path.read_text(encoding="utf-8")
            )
            if pivot_content:
                wide_path.write_text(pivot_content, encoding="utf-8")
                raw_path.unlink(missing_ok=True)
                return True, pivot_warning

            if wide_path.exists():
                wide_path.unlink()
            raw_path.replace(wide_path)
            raw_path.unlink(missing_ok=True)
            fallback_warning = pivot_warning or f"WIDE_CONVERSION_SKIPPED: {output_name}"
            return True, fallback_warning

        if wide_path.exists():
            wide_path.unlink()
        raw_path.replace(wide_path)
        return True, None
    except Exception as e:
        try:
            if wide_path.exists():
                raw_path.unlink(missing_ok=True)
                return True, f"WIDE_CONVERSION_FALLBACK_TO_EXPORT_PIVOT: {output_name}: {e}"
        except Exception:
            pass
        return False, f"WIDE_CONVERSION_FAILED: {output_name}: {e}"


def _copy_profile_artifacts(
    *,
    output_dir: Path,
    output_tag: str,
    manifest_path: Path | None,
    assertions_path: Path | None = None,
) -> dict[str, str]:
    profile_dir = output_dir / "profile"
    if not profile_dir.exists():
        return {}

    tag = _safe_filename(output_tag)
    out: dict[str, str] = {}

    if manifest_path and manifest_path.exists():
        dst = profile_dir / f"manifest_{tag}.json"
        try:
            import shutil

            shutil.copy2(manifest_path, dst)
            out["manifest_path"] = str(dst.relative_to(output_dir))
        except Exception:
            pass

    assertions_src = assertions_path if assertions_path and assertions_path.exists() else profile_dir / "assertions.json"
    if assertions_src.exists():
        dst = profile_dir / f"assertions_{tag}.json"
        try:
            import shutil

            shutil.copy2(assertions_src, dst)
            out["assertions_path"] = str(dst.relative_to(output_dir))
        except Exception:
            pass

    return out


def _load_resolved_params_from_path(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(payload, dict):
        return []

    raw_from_file = payload.get("resolved_params")
    if not isinstance(raw_from_file, list):
        return []
    return [item for item in raw_from_file if isinstance(item, dict)]


def _optional_result_path(export_result: dict[str, Any], key: str) -> Path | None:
    value = export_result.get(key)
    if not isinstance(value, str) or not value:
        return None
    return Path(value)


def _resolved_result_path(output_dir: Path, export_result: dict[str, Any], key: str) -> Path | None:
    raw_path = _optional_result_path(export_result, key)
    if raw_path is None:
        return None
    return _resolve_output_artifact_path(output_dir, str(raw_path))


def _load_resolved_params(
    *, output_dir: Path, export_result: dict[str, Any], assertions_rel_path: str | None
) -> list[dict[str, Any]]:
    raw_params = export_result.get("resolved_params")
    if isinstance(raw_params, list):
        return [item for item in raw_params if isinstance(item, dict)]

    direct_assertions_path = export_result.get("assertions_path")
    if isinstance(direct_assertions_path, str) and direct_assertions_path:
        resolved_direct = _resolve_output_artifact_path(output_dir, direct_assertions_path)
        if resolved_direct is not None and resolved_direct.exists():
            return _load_resolved_params_from_path(resolved_direct)

    if not assertions_rel_path:
        return []

    resolved = _resolve_output_artifact_path(output_dir, assertions_rel_path)
    if resolved is None or not resolved.exists():
        return []
    return _load_resolved_params_from_path(resolved)


def _export_audit_fields(
    *,
    output_dir: Path,
    export_result: dict[str, Any],
    source_key: str,
    source_display_name: str,
    view_luid: str,
    assertions_rel_path: str | None,
) -> dict[str, Any]:
    resolved_params = _load_resolved_params(
        output_dir=output_dir,
        export_result=export_result,
        assertions_rel_path=assertions_rel_path,
    )
    extra: dict[str, Any] = {
        "source_key": source_key,
        "source_display_name": source_display_name,
        "view_luid": view_luid,
        "resolved_params": resolved_params,
    }
    return extra


def _has_required_profile_artifacts(artifacts: dict[str, Any]) -> bool:
    manifest_path = artifacts.get("manifest_path")
    assertions_path = artifacts.get("assertions_path")
    return (
        isinstance(manifest_path, str)
        and bool(manifest_path)
        and isinstance(assertions_path, str)
        and bool(assertions_path)
    )


def _has_required_profile_sources(export_result: dict[str, Any]) -> bool:
    manifest_path = export_result.get("manifest_path")
    return isinstance(manifest_path, str) and bool(manifest_path)


def _can_materialize_required_profile_artifacts(
    *, output_dir: Path, export_result: dict[str, Any]
) -> bool:
    if not _has_required_profile_sources(export_result):
        return False

    manifest_src = _resolved_result_path(output_dir, export_result, "manifest_path")
    if manifest_src is None or not manifest_src.exists():
        return False

    resolved_assertions = _resolved_result_path(output_dir, export_result, "assertions_path")
    if resolved_assertions is not None and resolved_assertions.exists():
        return True

    generic_assertions = output_dir / "profile" / "assertions.json"
    return generic_assertions.exists()


def _summarize_view_result(
    *,
    entry_id: str,
    display_name: str,
    status: str,
    file_path: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    view_entry: dict[str, Any] = {
        "id": entry_id,
        "display_name": display_name,
        "status": status,
    }
    if file_path:
        view_entry["file_path"] = file_path
    if error:
        view_entry["error"] = error
    if extra:
        view_entry.update(extra)
    return view_entry


def _registry_tableau_metadata(
    entry: dict[str, Any],
    *,
    view: dict[str, Any] | None = None,
) -> dict[str, str]:
    tableau = entry.get("tableau") if isinstance(entry, dict) else {}
    metadata: dict[str, str] = {}
    if isinstance(tableau, dict):
        for key in ("workbook_name", "content_url"):
            value = tableau.get(key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        view_name = tableau.get("view_name")
        if isinstance(view_name, str) and view_name.strip():
            metadata["view_name"] = view_name.strip()

    if view:
        view_name = view.get("display_name") or view.get("view_name") or view.get("key")
        if isinstance(view_name, str) and view_name.strip():
            metadata["view_name"] = view_name.strip()
        content_url = view.get("content_url")
        if isinstance(content_url, str) and content_url.strip():
            metadata["content_url"] = content_url.strip()

    return metadata


def _write_export_summary(output_dir: Path, export_summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "export_summary.json"
    existing: dict[str, Any] = {}
    if summary_path.exists():
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except (json.JSONDecodeError, OSError):
            existing = {}

    merged = dict(existing)
    merged.update(export_summary)

    existing_views = existing.get("views")
    incoming_views = export_summary.get("views")
    if isinstance(existing_views, list) and isinstance(incoming_views, list):
        merged_views: list[dict[str, Any]] = [item for item in existing_views if isinstance(item, dict)]
        seen: set[str] = set()
        for item in merged_views:
            marker = json.dumps(
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "file_path": item.get("file_path"),
                    "manifest_path": item.get("manifest_path"),
                    "assertions_path": item.get("assertions_path"),
                    "resolved_params": item.get("resolved_params"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            seen.add(marker)

        for item in incoming_views:
            if not isinstance(item, dict):
                continue
            marker = json.dumps(
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "file_path": item.get("file_path"),
                    "manifest_path": item.get("manifest_path"),
                    "assertions_path": item.get("assertions_path"),
                    "resolved_params": item.get("resolved_params"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if marker in seen:
                continue
            seen.add(marker)
            merged_views.append(item)

        merged["views"] = merged_views
        merged["views_total"] = len(merged_views)
        merged["views_success"] = sum(1 for item in merged_views if item.get("status") == "success")
        merged["views_failed"] = sum(1 for item in merged_views if item.get("status") != "success")
        merged["success"] = bool(merged_views) and merged["views_failed"] == 0

    summary_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def _discover_context_artifacts(output_dir: Path | None) -> dict[str, str]:
    if output_dir is None:
        return {}
    artifacts: dict[str, str] = {}
    source_context_path = output_dir / "source_context.json"
    context_injection_path = output_dir / "context_injection.md"
    if source_context_path.exists():
        artifacts["source_context_path"] = str(source_context_path.relative_to(output_dir))
    if context_injection_path.exists():
        artifacts["context_injection_path"] = str(context_injection_path.relative_to(output_dir))
    return artifacts


def _emit(output_dir: Path | None, export_summary: dict[str, Any]) -> NoReturn:
    write_error: str | None = None
    if output_dir:
        try:
            export_summary = {**_discover_context_artifacts(output_dir), **export_summary}
            _write_export_summary(output_dir, export_summary)
        except Exception as e:
            write_error = str(e)

    payload = dict(export_summary)
    payload.update(_discover_context_artifacts(output_dir))
    if write_error:
        payload["success"] = False
        payload["export_summary_write_error"] = write_error

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if export_summary.get("success") and not write_error else 1)


def _error_summary(
    *,
    source_id: str,
    entry_type: str,
    display_name: str,
    error: str,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "source_id": source_id,
        "type": entry_type,
        "display_name": display_name,
        "timestamp": _now_iso(),
        "views_total": 0,
        "views_success": 0,
        "views_failed": 0,
        "views": [],
        "error": error,
    }
    if error_code:
        payload["error_code"] = error_code
    if extra:
        payload.update(extra)
    return payload


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-click Tableau export by source_id (registry.db)")
    parser.add_argument(
        "--source-id",
        required=True,
        help="必须精确匹配 registry.db entries[*].source_id",
    )
    parser.add_argument(
        "--views",
        help="Domain 类型必填：逗号分隔的 view_id（保持顺序）",
    )
    parser.add_argument("--vf", dest="vf_filters", action="append", help='筛选器：KEY=VALUE，可重复传入')
    parser.add_argument("--vp", dest="vp_filters", action="append", help='参数：KEY=VALUE，可重复传入')

    parser.add_argument(
        "--output-dir",
        help="输出目录（覆盖默认 jobs/{SESSION_ID}）；建议使用工作空间下的 jobs/<session_id>/",
    )
    parser.add_argument(
        "--session-id",
        help="用于推导默认输出目录 jobs/<session_id>/（仅在未提供 --output-dir 时生效）",
    )

    return parser.parse_args()


def main() -> None:
    args = _build_args()
    output_dir: Path | None = None
    display_name = args.source_id
    entry_type = "unknown"
    results: list[dict[str, Any]] = []

    try:
        output_dir = _resolve_output_dir(args.output_dir, args.session_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        repo_root = _repo_root()
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

        try:
            registry = _load_registry()
        except Exception as e:
            _emit(
                output_dir,
                _error_summary(
                    source_id=args.source_id,
                    entry_type=entry_type,
                    display_name=display_name,
                    error=str(e),
                    error_code="REGISTRY_LOAD_FAILED",
                ),
            )

        entry = _get_entry_by_source_id(registry, source_id=args.source_id)
        if not entry:
            any_entry = _get_any_entry_by_source_id(registry, source_id=args.source_id)
            if isinstance(any_entry, dict) and not _is_active_entry(any_entry):
                _emit(
                    output_dir,
                    _error_summary(
                        source_id=args.source_id,
                        entry_type=str(any_entry.get("type") or "view"),
                        display_name=str(any_entry.get("display_name") or args.source_id),
                        error=f"数据源已停用：{args.source_id}",
                        error_code="SOURCE_DEPRECATED",
                    ),
                )
            source_ids = _available_source_ids(registry)
            _emit(
                output_dir,
                _error_summary(
                    source_id=args.source_id,
                    entry_type=entry_type,
                    display_name=display_name,
                    error=f"未在 registry.db 找到 source_id：{args.source_id}",
                    error_code="SOURCE_ID_NOT_FOUND",
                    extra={"available_source_ids_count": len(source_ids), "available_source_ids": source_ids[:50]},
                ),
            )

        entry_type = str(entry.get("type") or "view")
        display_name = str(entry.get("display_name") or args.source_id)
        source_alias = _source_alias(entry)

        try:
            source_context = build_source_context(entry)
            write_source_context_bundle(output_dir, source_context)
        except Exception:
            # 上下文包是增强项，不阻断正式导出
            pass

        from export import export_view

        if entry_type == "domain":
            try:
                view_ids = _parse_views_arg(args.views)
            except ValueError as e:
                _emit(
                    output_dir,
                    _error_summary(
                        source_id=args.source_id,
                        entry_type="domain",
                        display_name=display_name,
                        error=str(e),
                        error_code="DUPLICATE_VIEWS",
                    ),
                )

            if not view_ids:
                _emit(
                    output_dir,
                    _error_summary(
                        source_id=args.source_id,
                        entry_type="domain",
                        display_name=display_name,
                        error="domain 类型必须提供 --views（逗号分隔，如 tableau.example_dashboard.sheet0）",
                        error_code="VIEWS_REQUIRED",
                    ),
                )

            try:
                selected_views = _selected_domain_views(entry, view_ids=view_ids)
            except ValueError as e:
                error_code = "DOMAIN_VIEWS_INVALID" if "views 必须是 list" in str(e) else "VIEW_ID_NOT_FOUND"
                error_extra = None
                if error_code == "VIEW_ID_NOT_FOUND":
                    views = entry.get("views") or []
                    allowed = [
                        view.get("view_id")
                        for view in views
                        if isinstance(view, dict) and isinstance(view.get("view_id"), str)
                    ]
                    error_extra = {"allowed_view_ids": allowed}
                _emit(
                    output_dir,
                    _error_summary(
                        source_id=args.source_id,
                        entry_type="domain",
                        display_name=display_name,
                        error=str(e),
                        error_code=error_code,
                        extra=error_extra,
                    ),
                )

            budget_ok, budget = _ensure_export_budget(
                output_dir=output_dir,
                source_id=args.source_id,
                required_success_quota=len(selected_views),
            )
            if not budget_ok:
                _emit(
                    output_dir,
                    _error_summary(
                        source_id=args.source_id,
                        entry_type="domain",
                        display_name=display_name,
                        error="EXPORT_BUDGET_EXCEEDED",
                        error_code="EXPORT_BUDGET_EXCEEDED",
                        extra={"budget": budget},
                    ),
                )

            budget_path = _export_budget_path(output_dir)
            budget_state = budget

            from auth import get_auth

            try:
                auth = get_auth()
            except SystemExit as e:
                err = f"Tableau 认证初始化失败（get_auth 退出，code={e.code}）"
                for view in selected_views:
                    view_id = str(view.get("view_id") or "")
                    view_alias = _view_alias(view)
                    view_display = str(view.get("display_name") or view_alias or view_id)
                    results.append(
                        _summarize_view_result(
                            entry_id=view_id,
                            display_name=view_display,
                            status="failed",
                            error=err,
                        )
                    )
                    budget_state = _record_export_budget(
                        budget_path,
                        budget_state,
                        success=False,
                        source_id=args.source_id,
                        view_id=view_id,
                        view_luid=(
                            view.get("view_luid") if isinstance(view.get("view_luid"), str) else None
                        ),
                    )
            else:
                try:
                    try:
                        with redirect_stdout(sys.stderr):
                            auth.signin()
                    except Exception as e:
                        _emit(
                            output_dir,
                            _error_summary(
                                source_id=args.source_id,
                                entry_type="domain",
                                display_name=display_name,
                                error=f"DOMAIN_AUTH_FAILED: {e}",
                                error_code="DOMAIN_AUTH_FAILED",
                            ),
                        )

                    for view in selected_views:
                        view_id = str(view.get("view_id") or "")
                        view_alias = _view_alias(view)
                        view_display = str(view.get("display_name") or view_alias or view_id)
                        view_luid = view.get("view_luid")
                        base_output_name = _output_name_for_view(
                            source_id=args.source_id, view_id=view_id
                        )
                        output_name = _allocate_unique_output_name(
                            output_dir=output_dir,
                            base_output_name=base_output_name,
                            vf_filters=args.vf_filters,
                            vp_filters=args.vp_filters,
                        )

                        if not isinstance(view_luid, str) or not view_luid:
                            results.append(
                                _summarize_view_result(
                                    entry_id=view_id,
                                    display_name=view_display,
                                    status="failed",
                                    error="registry domain view 缺少 view_luid",
                                )
                            )
                            budget_state = _record_export_budget(
                                budget_path,
                                budget_state,
                                success=False,
                                source_id=args.source_id,
                                view_id=view_id,
                                view_luid=None,
                            )
                            continue

                        with redirect_stdout(sys.stderr):
                            export_result = export_view(
                                view_url=view_id,
                                output_dir=str(output_dir),
                                view_luid=view_luid,
                                vf_filters=args.vf_filters,
                                vp_filters=args.vp_filters,
                                output_name=output_name,
                                auth=auth,
                                source_key=source_alias,
                                source_display_name=display_name,
                                tableau_metadata=_registry_tableau_metadata(entry, view=view),
                            )

                        if not export_result.get("success"):
                            _cleanup_failed_export_artifacts(
                                output_dir=output_dir,
                                output_name=output_name,
                                result=export_result,
                            )
                            results.append(
                                _summarize_view_result(
                                    entry_id=view_id,
                                    display_name=view_display,
                                    status="failed",
                                    error=str(export_result.get("error") or "Unknown error"),
                                )
                            )
                            budget_state = _record_export_budget(
                                budget_path,
                                budget_state,
                                success=False,
                                source_id=args.source_id,
                                view_id=view_id,
                                view_luid=view_luid,
                            )
                            continue
                        if not _can_materialize_required_profile_artifacts(
                            output_dir=output_dir,
                            export_result=export_result,
                        ):
                            _cleanup_failed_export_artifacts(
                                output_dir=output_dir,
                                output_name=output_name,
                                result=export_result,
                            )
                            results.append(
                                _summarize_view_result(
                                    entry_id=view_id,
                                    display_name=view_display,
                                    status="failed",
                                    error="PROFILE_ARTIFACTS_MISSING",
                                )
                            )
                            budget_state = _record_export_budget(
                                budget_path,
                                budget_state,
                                success=False,
                                source_id=args.source_id,
                                view_id=view_id,
                                view_luid=view_luid,
                            )
                            continue

                        raw_path = _resolved_result_path(output_dir, export_result, "csv_path")
                        wide_path = _final_wide_path(output_dir, output_name)
                        if raw_path is None or not raw_path.exists():
                            _cleanup_failed_export_artifacts(
                                output_dir=output_dir,
                                output_name=output_name,
                                result=export_result,
                            )
                            results.append(
                                _summarize_view_result(
                                    entry_id=view_id,
                                    display_name=view_display,
                                    status="failed",
                                    error="RAW_CSV_MISSING",
                                )
                            )
                            budget_state = _record_export_budget(
                                budget_path,
                                budget_state,
                                success=False,
                                source_id=args.source_id,
                                view_id=view_id,
                                view_luid=view_luid,
                            )
                            continue

                        ok, wide_note = _convert_or_rename_to_wide(
                            raw_path=raw_path,
                            wide_path=wide_path,
                            output_name=output_name,
                        )
                        if not ok:
                            _cleanup_failed_export_artifacts(
                                output_dir=output_dir,
                                output_name=output_name,
                                result=export_result,
                            )
                            results.append(
                                _summarize_view_result(
                                    entry_id=view_id,
                                    display_name=view_display,
                                    status="failed",
                                    error=wide_note or "WIDE_CONVERSION_FAILED",
                                )
                            )
                            budget_state = _record_export_budget(
                                budget_path,
                                budget_state,
                                success=False,
                                source_id=args.source_id,
                                view_id=view_id,
                                view_luid=view_luid,
                            )
                            continue

                        pivot_file = _resolved_result_path(output_dir, export_result, "pivot_path")
                        if pivot_file is not None and pivot_file.exists():
                            if pivot_file.resolve() != wide_path.resolve():
                                pivot_file.unlink(missing_ok=True)

                        domain_profile_artifacts: dict[str, Any] = _copy_profile_artifacts(
                            output_dir=output_dir,
                            output_tag=output_name,
                            manifest_path=_resolved_result_path(output_dir, export_result, "manifest_path"),
                            assertions_path=_resolved_result_path(output_dir, export_result, "assertions_path"),
                        )
                        domain_profile_artifacts.update(
                            _export_audit_fields(
                                output_dir=output_dir,
                                export_result=export_result,
                                source_key=source_alias,
                                source_display_name=display_name,
                                view_luid=view_luid,
                                assertions_rel_path=domain_profile_artifacts.get("assertions_path"),
                            )
                        )
                        if not _has_required_profile_artifacts(domain_profile_artifacts):
                            _cleanup_failed_export_artifacts(
                                output_dir=output_dir,
                                output_name=output_name,
                                result=export_result,
                            )
                            results.append(
                                _summarize_view_result(
                                    entry_id=view_id,
                                    display_name=view_display,
                                    status="failed",
                                    error="PROFILE_ARTIFACTS_MISSING",
                                )
                            )
                            budget_state = _record_export_budget(
                                budget_path,
                                budget_state,
                                success=False,
                                source_id=args.source_id,
                                view_id=view_id,
                                view_luid=view_luid,
                            )
                            continue
                        if wide_note:
                            domain_profile_artifacts["wide_warning"] = wide_note
                        tableau_meta = export_result.get("tableau")
                        if isinstance(tableau_meta, dict) and tableau_meta:
                            domain_profile_artifacts["tableau"] = tableau_meta

                        results.append(
                            _summarize_view_result(
                                entry_id=view_id,
                                display_name=view_display,
                                status="success",
                                file_path=str(wide_path.relative_to(output_dir)),
                                extra=domain_profile_artifacts,
                            )
                        )
                        budget_state = _record_export_budget(
                            budget_path,
                            budget_state,
                            success=True,
                            source_id=args.source_id,
                            view_id=view_id,
                            view_luid=view_luid,
                        )
                finally:
                    with redirect_stdout(sys.stderr):
                        auth.signout()

            export_summary = {
                "success": all(item.get("status") == "success" for item in results) and bool(results),
                "source_id": args.source_id,
                "type": "domain",
                "display_name": display_name,
                "tableau": _registry_tableau_metadata(entry),
                "budget": budget_state,
                "timestamp": _now_iso(),
                "views_total": len(results),
                "views_success": sum(1 for item in results if item.get("status") == "success"),
                "views_failed": sum(1 for item in results if item.get("status") != "success"),
                "views": results,
            }
            _emit(output_dir, export_summary)

        tableau = entry.get("tableau") or {}
        view_luid = tableau.get("view_luid") if isinstance(tableau, dict) else None
        if not isinstance(view_luid, str) or not view_luid:
            _emit(
                output_dir,
                _error_summary(
                    source_id=args.source_id,
                    entry_type="view",
                    display_name=display_name,
                    error="registry.db view 条目缺少 tableau.view_luid",
                    error_code="VIEW_LUID_MISSING",
                ),
            )

        budget_ok, budget = _ensure_export_budget(
            output_dir=output_dir,
            source_id=args.source_id,
            required_success_quota=1,
        )
        if not budget_ok:
            _emit(
                output_dir,
                _error_summary(
                    source_id=args.source_id,
                    entry_type="view",
                    display_name=display_name,
                    error="EXPORT_BUDGET_EXCEEDED",
                    error_code="EXPORT_BUDGET_EXCEEDED",
                    extra={"budget": budget},
                ),
            )

        budget_path = _export_budget_path(output_dir)
        budget_state = budget

        base_output_name = _output_name_for_source(source_id=args.source_id)
        output_name = _allocate_unique_output_name(
            output_dir=output_dir,
            base_output_name=base_output_name,
            vf_filters=args.vf_filters,
            vp_filters=args.vp_filters,
        )
        with redirect_stdout(sys.stderr):
            export_result = export_view(
                view_url=args.source_id,
                output_dir=str(output_dir),
                view_luid=view_luid,
                vf_filters=args.vf_filters,
                vp_filters=args.vp_filters,
                output_name=output_name,
                source_key=source_alias,
                source_display_name=display_name,
                tableau_metadata=_registry_tableau_metadata(entry),
            )

        if not export_result.get("success"):
            budget_state = _record_export_budget(
                budget_path,
                budget_state,
                success=False,
                source_id=args.source_id,
                view_id=args.source_id,
                view_luid=view_luid,
            )
            _cleanup_failed_export_artifacts(
                output_dir=output_dir,
                output_name=output_name,
                result=export_result,
            )
            _emit(
                output_dir,
                {
                    "success": False,
                    "source_id": args.source_id,
                    "type": "view",
                    "display_name": display_name,
                    "tableau": _registry_tableau_metadata(entry),
                    "budget": budget_state,
                    "timestamp": _now_iso(),
                    "views_total": 1,
                    "views_success": 0,
                    "views_failed": 1,
                    "views": [
                        _summarize_view_result(
                            entry_id=args.source_id,
                            display_name=display_name,
                            status="failed",
                            error=str(export_result.get("error") or "Unknown error"),
                        )
                    ],
                },
            )
        if not _can_materialize_required_profile_artifacts(
            output_dir=output_dir,
            export_result=export_result,
        ):
            _cleanup_failed_export_artifacts(
                output_dir=output_dir,
                output_name=output_name,
                result=export_result,
            )
            _emit(
                output_dir,
                {
                    "success": False,
                    "source_id": args.source_id,
                    "type": "view",
                    "display_name": display_name,
                    "timestamp": _now_iso(),
                    "views_total": 1,
                    "views_success": 0,
                    "views_failed": 1,
                    "views": [
                        _summarize_view_result(
                            entry_id=args.source_id,
                            display_name=display_name,
                            status="failed",
                            error="PROFILE_ARTIFACTS_MISSING",
                        )
                    ],
                },
            )

        raw_path = _resolved_result_path(output_dir, export_result, "csv_path")
        wide_path = _final_wide_path(output_dir, output_name)
        if raw_path is None or not raw_path.exists():
            _cleanup_failed_export_artifacts(
                output_dir=output_dir,
                output_name=output_name,
                result=export_result,
            )
            _emit(
                output_dir,
                {
                    "success": False,
                    "source_id": args.source_id,
                    "type": "view",
                    "display_name": display_name,
                    "timestamp": _now_iso(),
                    "views_total": 1,
                    "views_success": 0,
                    "views_failed": 1,
                    "views": [
                        _summarize_view_result(
                            entry_id=args.source_id,
                            display_name=display_name,
                            status="failed",
                            error="RAW_CSV_MISSING",
                        )
                    ],
                },
            )

        ok, wide_note = _convert_or_rename_to_wide(
            raw_path=raw_path,
            wide_path=wide_path,
            output_name=output_name,
        )
        if not ok:
            _cleanup_failed_export_artifacts(
                output_dir=output_dir,
                output_name=output_name,
                result=export_result,
            )
            _emit(
                output_dir,
                {
                    "success": False,
                    "source_id": args.source_id,
                    "type": "view",
                    "display_name": display_name,
                    "timestamp": _now_iso(),
                    "views_total": 1,
                    "views_success": 0,
                    "views_failed": 1,
                    "views": [
                        _summarize_view_result(
                            entry_id=args.source_id,
                            display_name=display_name,
                            status="failed",
                            error=wide_note or "WIDE_CONVERSION_FAILED",
                        )
                    ],
                },
            )

        pivot_file = _resolved_result_path(output_dir, export_result, "pivot_path")
        if pivot_file is not None and pivot_file.exists():
            if pivot_file.resolve() != wide_path.resolve():
                pivot_file.unlink(missing_ok=True)

        view_profile_artifacts: dict[str, Any] = _copy_profile_artifacts(
            output_dir=output_dir,
            output_tag=output_name,
            manifest_path=_resolved_result_path(output_dir, export_result, "manifest_path"),
            assertions_path=_resolved_result_path(output_dir, export_result, "assertions_path"),
        )
        view_profile_artifacts.update(
            _export_audit_fields(
                output_dir=output_dir,
                export_result=export_result,
                source_key=source_alias,
                source_display_name=display_name,
                view_luid=view_luid,
                assertions_rel_path=view_profile_artifacts.get("assertions_path"),
            )
        )
        if not _has_required_profile_artifacts(view_profile_artifacts):
            _cleanup_failed_export_artifacts(
                output_dir=output_dir,
                output_name=output_name,
                result=export_result,
            )
            _emit(
                output_dir,
                {
                    "success": False,
                    "source_id": args.source_id,
                    "type": "view",
                    "display_name": display_name,
                    "timestamp": _now_iso(),
                    "views_total": 1,
                    "views_success": 0,
                    "views_failed": 1,
                    "views": [
                        _summarize_view_result(
                            entry_id=args.source_id,
                            display_name=display_name,
                            status="failed",
                            error="PROFILE_ARTIFACTS_MISSING",
                        )
                    ],
                },
            )
        if wide_note:
            view_profile_artifacts["wide_warning"] = wide_note
        tableau_meta = export_result.get("tableau")
        if isinstance(tableau_meta, dict) and tableau_meta:
            view_profile_artifacts["tableau"] = tableau_meta

        _emit(
            output_dir,
            {
                "success": True,
                "source_id": args.source_id,
                "type": "view",
                "display_name": display_name,
                "tableau": _registry_tableau_metadata(entry),
                "timestamp": _now_iso(),
                "views_total": 1,
                "views_success": 1,
                "views_failed": 0,
                "views": [
                    _summarize_view_result(
                        entry_id=args.source_id,
                        display_name=display_name,
                        status="success",
                        file_path=str(wide_path.relative_to(output_dir)),
                        extra=view_profile_artifacts,
                    )
                ],
            },
        )
    except SystemExit:
        raise
    except Exception as e:
        views_success = sum(1 for item in results if item.get("status") == "success")
        _emit(
            output_dir,
            {
                "success": False,
                "source_id": args.source_id,
                "type": entry_type,
                "display_name": display_name,
                "timestamp": _now_iso(),
                "views_total": len(results),
                "views_success": views_success,
                "views_failed": len(results) - views_success,
                "views": results,
                "error": str(e),
            },
        )


if __name__ == "__main__":
    main()
