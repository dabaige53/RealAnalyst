#!/usr/bin/env python3
"""Read and update RealAnalyst job manifests.

The manifest is the job-level ledger for artifacts and user-facing state. It
indexes files; it does not replace large data, profile, report, or log files.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_NAME = "job_manifest.json"
SCHEMA_VERSION = "1.0"
USER_VISIBLE_ROLES = {"user_deliverable", "user_attachment"}
ARTIFACT_ROLES = {
    "user_deliverable",
    "user_attachment",
    "supporting_evidence",
    "raw_input",
    "derived_internal",
    "audit_log",
    "legacy",
    "deprecated",
    "unknown_legacy",
}
ARTIFACT_KINDS = {"report", "csv", "json", "markdown", "log", "archive", "directory", "other"}
ARTIFACT_STATUSES = {"ready", "superseded", "failed", "archived"}
JOB_STATUSES = {"planning", "running", "ready_for_review", "delivered", "failed", "archived"}
VERIFICATION_STATUSES = {"passed", "warning", "failed", "not_run"}
STEP_STATUSES = {"success", "warning", "failed", "skipped", "running"}


class JobManifestError(ValueError):
    """Raised when a job manifest request violates the manifest contract."""

    def __init__(self, message: str, *, error_code: str = "JOB_MANIFEST_INVALID") -> None:
        super().__init__(message)
        self.error_code = error_code


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _as_job_dir(job_dir: str | Path) -> Path:
    return Path(job_dir).expanduser().resolve()


def manifest_path(job_dir: str | Path) -> Path:
    return _as_job_dir(job_dir) / MANIFEST_NAME


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(encoded)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _relative_job_path(job_dir: Path, raw_path: str | Path) -> str:
    raw = Path(raw_path)
    if raw.is_absolute():
        raise JobManifestError(
            f"artifact path must be relative to job_dir: {raw_path}",
            error_code="JOB_MANIFEST_PATH_ESCAPE",
        )
    if not str(raw).strip():
        raise JobManifestError("artifact path is required", error_code="JOB_MANIFEST_PATH_INVALID")
    candidate = (job_dir / raw).resolve()
    try:
        relative = candidate.relative_to(job_dir.resolve())
    except ValueError as exc:
        raise JobManifestError(
            f"artifact path escapes job_dir: {raw_path}",
            error_code="JOB_MANIFEST_PATH_ESCAPE",
        ) from exc
    if str(relative) == ".":
        raise JobManifestError("artifact path cannot point to job_dir", error_code="JOB_MANIFEST_PATH_INVALID")
    return relative.as_posix()


def default_manifest(*, job_id: str, title: str = "", owner_skill: str = "analysis-run", business_context: str = "") -> dict[str, Any]:
    now = _now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "job": {
            "id": job_id,
            "title": title or job_id,
            "status": "planning",
            "created_at": now,
            "updated_at": now,
            "owner_skill": owner_skill,
            "business_context": business_context,
        },
        "user_surface": {
            "summary": "",
            "primary_deliverable_id": None,
            "deliverables": [],
            "verification_status": "not_run",
            "risks": [],
            "next_actions": [],
            "display_language": "zh-CN",
            "technical_details_available": True,
        },
        "inputs": [],
        "steps": [],
        "artifacts": [],
        "verification": {},
        "planning": {
            "selected_framework_id": None,
            "selected_analysis_mode": None,
            "selected_delivery_mode": None,
            "selected_report_template": None,
            "plan_artifact_id": None,
        },
        "provenance": {},
        "reply_policy": {
            "default_mode": "business",
            "hide_internal_paths": True,
            "hide_source_keys": True,
            "hide_script_names": True,
            "allow_technical_details_when_requested": True,
            "redaction_notes": [],
        },
        "archive": {},
        "legacy": {},
    }


def validate_manifest_payload(payload: dict[str, Any], *, job_dir: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["manifest must be a JSON object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    job = payload.get("job")
    if not isinstance(job, dict):
        errors.append("job must be an object")
    else:
        for field in ("id", "title", "status", "created_at", "updated_at"):
            if field not in job:
                errors.append(f"job.{field} is required")
        if job.get("status") not in JOB_STATUSES:
            errors.append(f"job.status must be one of {sorted(JOB_STATUSES)}")

    user_surface = payload.get("user_surface")
    if not isinstance(user_surface, dict):
        errors.append("user_surface must be an object")
    else:
        if user_surface.get("verification_status") not in VERIFICATION_STATUSES:
            errors.append(f"user_surface.verification_status must be one of {sorted(VERIFICATION_STATUSES)}")
        for field in ("deliverables", "risks", "next_actions"):
            if not isinstance(user_surface.get(field), list):
                errors.append(f"user_surface.{field} must be a list")

    for list_field in ("inputs", "steps", "artifacts"):
        if not isinstance(payload.get(list_field), list):
            errors.append(f"{list_field} must be a list")

    if not isinstance(payload.get("reply_policy"), dict):
        errors.append("reply_policy must be an object")

    planning = payload.get("planning")
    if planning is not None:
        if not isinstance(planning, dict):
            errors.append("planning must be an object")
        else:
            for field in (
                "selected_framework_id",
                "selected_analysis_mode",
                "selected_delivery_mode",
                "selected_report_template",
                "plan_artifact_id",
            ):
                if field in planning and planning.get(field) is not None and not isinstance(planning.get(field), str):
                    errors.append(f"planning.{field} must be a string or null")

    if isinstance(payload.get("steps"), list):
        seen_steps: set[str] = set()
        for index, step in enumerate(payload["steps"]):
            if not isinstance(step, dict):
                errors.append(f"steps[{index}] must be an object")
                continue
            step_id = str(step.get("id") or "")
            if not step_id:
                errors.append(f"steps[{index}].id is required")
            elif step_id in seen_steps:
                errors.append(f"steps[{index}].id duplicates {step_id}")
            seen_steps.add(step_id)
            for field in ("name", "owner_skill"):
                if field not in step:
                    errors.append(f"steps[{index}].{field} is required")
            if step.get("status") not in STEP_STATUSES:
                errors.append(f"steps[{index}].status must be one of {sorted(STEP_STATUSES)}")
            for field in ("input_artifacts", "output_artifacts"):
                if not isinstance(step.get(field), list):
                    errors.append(f"steps[{index}].{field} must be a list")

    if isinstance(payload.get("artifacts"), list):
        seen_artifacts: set[str] = set()
        resolved_job_dir = _as_job_dir(job_dir) if job_dir is not None else None
        for index, artifact in enumerate(payload["artifacts"]):
            if not isinstance(artifact, dict):
                errors.append(f"artifacts[{index}] must be an object")
                continue
            artifact_id = str(artifact.get("id") or "")
            if not artifact_id:
                errors.append(f"artifacts[{index}].id is required")
            elif artifact_id in seen_artifacts:
                errors.append(f"artifacts[{index}].id duplicates {artifact_id}")
            seen_artifacts.add(artifact_id)
            if artifact.get("role") not in ARTIFACT_ROLES:
                errors.append(f"artifacts[{index}].role must be one of {sorted(ARTIFACT_ROLES)}")
            if artifact.get("kind") not in ARTIFACT_KINDS:
                errors.append(f"artifacts[{index}].kind must be one of {sorted(ARTIFACT_KINDS)}")
            if artifact.get("status") not in ARTIFACT_STATUSES:
                errors.append(f"artifacts[{index}].status must be one of {sorted(ARTIFACT_STATUSES)}")
            for field in ("user_visible", "internal_only", "safe_to_archive", "safe_to_delete"):
                if not isinstance(artifact.get(field), bool):
                    errors.append(f"artifacts[{index}].{field} must be a boolean")
            if resolved_job_dir is not None:
                try:
                    _relative_job_path(resolved_job_dir, str(artifact.get("path") or ""))
                except JobManifestError as exc:
                    errors.append(f"artifacts[{index}].path: {exc}")
    return errors


def load_manifest(job_dir: str | Path) -> dict[str, Any]:
    path = manifest_path(job_dir)
    if not path.exists():
        raise JobManifestError(f"job manifest not found: {path}", error_code="JOB_MANIFEST_NOT_FOUND")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JobManifestError(f"job manifest is invalid JSON: {path}", error_code="JOB_MANIFEST_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise JobManifestError("job manifest must be a JSON object")
    errors = validate_manifest_payload(payload, job_dir=job_dir)
    if errors:
        raise JobManifestError("; ".join(errors))
    return payload


def create_manifest(
    job_dir: str | Path,
    *,
    job_id: str | None = None,
    title: str = "",
    owner_skill: str = "analysis-run",
    business_context: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    resolved_job_dir = _as_job_dir(job_dir)
    path = manifest_path(resolved_job_dir)
    if path.exists() and not overwrite:
        return load_manifest(resolved_job_dir)
    payload = default_manifest(
        job_id=job_id or resolved_job_dir.name,
        title=title,
        owner_skill=owner_skill,
        business_context=business_context,
    )
    _atomic_write_json(path, payload)
    return payload


def save_manifest(job_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    resolved_job_dir = _as_job_dir(job_dir)
    if isinstance(payload.get("job"), dict):
        payload["job"]["updated_at"] = _now_iso()
    errors = validate_manifest_payload(payload, job_dir=resolved_job_dir)
    if errors:
        raise JobManifestError("; ".join(errors))
    _atomic_write_json(manifest_path(resolved_job_dir), payload)
    return payload


def register_artifact(job_dir: str | Path, artifact: dict[str, Any]) -> dict[str, Any]:
    resolved_job_dir = _as_job_dir(job_dir)
    payload = load_manifest(resolved_job_dir)
    item = dict(artifact)
    item["path"] = _relative_job_path(resolved_job_dir, item.get("path", ""))
    item.setdefault("display_name", item["path"])
    item.setdefault("kind", "other")
    item.setdefault("role", "supporting_evidence")
    item.setdefault("user_visible", item["role"] in USER_VISIBLE_ROLES)
    item.setdefault("internal_only", not bool(item["user_visible"]))
    item.setdefault("producer", "")
    item.setdefault("consumers", [])
    item.setdefault("created_at", _now_iso())
    item.setdefault("status", "ready")
    item.setdefault("validation", {"status": "not_run"})
    item.setdefault("safe_to_archive", not bool(item["user_visible"]))
    item.setdefault("safe_to_delete", False)
    if not item.get("id"):
        raise JobManifestError("artifact.id is required")

    artifacts = [existing for existing in payload["artifacts"] if existing.get("id") != item["id"]]
    artifacts.append(item)
    payload["artifacts"] = artifacts

    if item["user_visible"] and item["role"] in USER_VISIBLE_ROLES:
        deliverables = list(payload["user_surface"].get("deliverables") or [])
        if item["id"] not in deliverables:
            deliverables.append(item["id"])
        payload["user_surface"]["deliverables"] = deliverables
        if item["role"] == "user_deliverable" and not payload["user_surface"].get("primary_deliverable_id"):
            payload["user_surface"]["primary_deliverable_id"] = item["id"]
    return save_manifest(resolved_job_dir, payload)


def register_step(job_dir: str | Path, step: dict[str, Any]) -> dict[str, Any]:
    payload = load_manifest(job_dir)
    item = dict(step)
    if not item.get("id"):
        raise JobManifestError("step.id is required")
    item.setdefault("name", item["id"])
    item.setdefault("owner_skill", "")
    item.setdefault("status", "success")
    item.setdefault("started_at", None)
    item.setdefault("finished_at", _now_iso() if item["status"] in {"success", "warning", "failed", "skipped"} else None)
    item.setdefault("input_artifacts", [])
    item.setdefault("output_artifacts", [])
    item.setdefault("error_code", None)
    item.setdefault("user_visible_summary", "")
    payload["steps"] = [existing for existing in payload["steps"] if existing.get("id") != item["id"]]
    payload["steps"].append(item)
    return save_manifest(job_dir, payload)


def update_user_surface(job_dir: str | Path, patch: dict[str, Any]) -> dict[str, Any]:
    payload = load_manifest(job_dir)
    user_surface = dict(payload["user_surface"])
    user_surface.update(patch)
    payload["user_surface"] = user_surface
    return save_manifest(job_dir, payload)


def update_planning(job_dir: str | Path, patch: dict[str, Any]) -> dict[str, Any]:
    payload = load_manifest(job_dir)
    planning = dict(payload.get("planning") if isinstance(payload.get("planning"), dict) else {})
    allowed = {
        "selected_framework_id",
        "framework_selection_reason",
        "selected_analysis_mode",
        "analysis_mode_selection_reason",
        "selected_delivery_mode",
        "delivery_mode_selection_reason",
        "selected_report_template",
        "template_selection_reason",
        "plan_artifact_id",
    }
    for key, value in patch.items():
        if key not in allowed:
            continue
        if value is not None and not isinstance(value, str):
            raise JobManifestError(f"planning.{key} must be a string or null")
        planning[key] = value
    payload["planning"] = planning
    return save_manifest(job_dir, payload)


def user_visible_artifacts(job_dir: str | Path) -> list[dict[str, Any]]:
    payload = load_manifest(job_dir)
    ids = set(payload["user_surface"].get("deliverables") or [])
    artifacts = [
        artifact
        for artifact in payload["artifacts"]
        if artifact.get("user_visible") is True
        and artifact.get("role") in USER_VISIBLE_ROLES
        and (not ids or artifact.get("id") in ids)
    ]
    order = {artifact_id: index for index, artifact_id in enumerate(payload["user_surface"].get("deliverables") or [])}
    return sorted(artifacts, key=lambda artifact: order.get(artifact.get("id"), len(order)))


def _emit(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def _error(exc: Exception) -> int:
    error_code = getattr(exc, "error_code", "JOB_MANIFEST_ERROR")
    return _emit({"success": False, "error": str(exc), "error_code": error_code}, exit_code=1)


def _load_json_arg(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise JobManifestError("argument must be valid JSON", error_code="JOB_MANIFEST_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise JobManifestError("argument must be a JSON object")
    return payload


def _read_manifest_without_validation(job_dir: str | Path) -> dict[str, Any]:
    path = manifest_path(job_dir)
    if not path.exists():
        raise JobManifestError(f"job manifest not found: {path}", error_code="JOB_MANIFEST_NOT_FOUND")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JobManifestError(f"job manifest is invalid JSON: {path}", error_code="JOB_MANIFEST_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise JobManifestError("job manifest must be a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage RealAnalyst job_manifest.json files.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a job manifest if missing.")
    init.add_argument("--job-dir", required=True)
    init.add_argument("--job-id")
    init.add_argument("--title", default="")
    init.add_argument("--owner-skill", default="analysis-run")
    init.add_argument("--business-context", default="")
    init.add_argument("--overwrite", action="store_true")

    register_art = sub.add_parser("register-artifact", help="Register or replace an artifact.")
    register_art.add_argument("--job-dir", required=True)
    register_art.add_argument("--artifact-json", required=True)

    register_st = sub.add_parser("register-step", help="Register or replace a step.")
    register_st.add_argument("--job-dir", required=True)
    register_st.add_argument("--step-json", required=True)

    user_surface = sub.add_parser("update-user-surface", help="Patch user_surface fields.")
    user_surface.add_argument("--job-dir", required=True)
    user_surface.add_argument("--patch-json", required=True)

    planning = sub.add_parser("update-planning", help="Patch planning decision fields.")
    planning.add_argument("--job-dir", required=True)
    planning.add_argument("--patch-json", required=True)

    summary = sub.add_parser("user-summary", help="Return user-facing summary and deliverables.")
    summary.add_argument("--job-dir", required=True)

    validate = sub.add_parser("validate", help="Validate a job manifest.")
    validate.add_argument("--job-dir", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            payload = create_manifest(
                args.job_dir,
                job_id=args.job_id,
                title=args.title,
                owner_skill=args.owner_skill,
                business_context=args.business_context,
                overwrite=args.overwrite,
            )
            return _emit({"success": True, "manifest_path": str(manifest_path(args.job_dir)), "manifest": payload})
        if args.command == "register-artifact":
            payload = register_artifact(args.job_dir, _load_json_arg(args.artifact_json))
            return _emit({"success": True, "manifest_path": str(manifest_path(args.job_dir)), "manifest": payload})
        if args.command == "register-step":
            payload = register_step(args.job_dir, _load_json_arg(args.step_json))
            return _emit({"success": True, "manifest_path": str(manifest_path(args.job_dir)), "manifest": payload})
        if args.command == "update-user-surface":
            payload = update_user_surface(args.job_dir, _load_json_arg(args.patch_json))
            return _emit({"success": True, "manifest_path": str(manifest_path(args.job_dir)), "manifest": payload})
        if args.command == "update-planning":
            payload = update_planning(args.job_dir, _load_json_arg(args.patch_json))
            return _emit({"success": True, "manifest_path": str(manifest_path(args.job_dir)), "manifest": payload})
        if args.command == "user-summary":
            payload = load_manifest(args.job_dir)
            return _emit(
                {
                    "success": True,
                    "manifest_path": str(manifest_path(args.job_dir)),
                    "user_surface": payload["user_surface"],
                    "deliverables": user_visible_artifacts(args.job_dir),
                }
            )
        if args.command == "validate":
            payload = _read_manifest_without_validation(args.job_dir)
            errors = validate_manifest_payload(payload, job_dir=args.job_dir)
            return _emit(
                {
                    "success": not errors,
                    "manifest_path": str(manifest_path(args.job_dir)),
                    "errors": errors,
                    "error_count": len(errors),
                },
                exit_code=0 if not errors else 1,
            )
        raise JobManifestError(f"unsupported command: {args.command}", error_code="JOB_MANIFEST_UNSUPPORTED_COMMAND")
    except Exception as exc:  # JSON-only failure contract for agent callers.
        return _error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
