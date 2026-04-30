#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil

from _common import (
    now_iso,
    read_json,
    relpath,
    runtime_refine_dir,
    source_refine_dir,
    upsert_job_artifact,
    workspace_path,
    write_json,
)


def rewrite_runtime_paths(value: object, *, refine_id: str) -> object:
    prefix = f"runtime/metadata-refine/{refine_id}/"
    if isinstance(value, str):
        if value.startswith(prefix):
            return value.replace("runtime/metadata-refine", "metadata/sources/refine", 1)
        return value
    if isinstance(value, list):
        return [rewrite_runtime_paths(item, refine_id=refine_id) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_runtime_paths(item, refine_id=refine_id) for key, item in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Move a metadata refinement pack from runtime into metadata/sources/refine.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--refine-id", required=True)
    parser.add_argument("--session-id", default="")
    args = parser.parse_args()

    workspace = workspace_path(args.workspace)
    src = runtime_refine_dir(workspace, args.refine_id)
    dst = source_refine_dir(workspace, args.refine_id)
    if not src.exists():
        raise SystemExit(f"runtime refine pack not found: {src}")
    if dst.exists():
        raise SystemExit(f"archive already exists: {dst}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))

    manifest_path = dst / "evidence_manifest.json"
    manifest = read_json(manifest_path)
    manifest.update(
        {
            "status": "archived_source",
            "archived_at": now_iso(),
            "archived_from": relpath(workspace, src),
            "archived_to": relpath(workspace, dst),
        }
    )
    rewritten = rewrite_runtime_paths(manifest, refine_id=args.refine_id)
    if not isinstance(rewritten, dict):
        raise SystemExit("invalid evidence manifest")
    manifest = rewritten
    write_json(manifest_path, manifest)

    if args.session_id.strip():
        upsert_job_artifact(
            workspace,
            args.session_id.strip(),
            {
                "path": relpath(workspace, manifest_path),
                "kind": "metadata_refine_reference",
                "role": "archive",
                "refine_id": args.refine_id,
                "source_job_id": args.session_id.strip(),
            },
        )

    print(
        json.dumps(
            {
                "success": True,
                "refine_id": args.refine_id,
                "archived_to": relpath(workspace, dst),
                "manifest": relpath(workspace, manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
