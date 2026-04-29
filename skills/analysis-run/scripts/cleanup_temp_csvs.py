#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_ROOT = _find_workspace_root(Path(__file__).resolve())
JOBS_ROOT = WORKSPACE_ROOT / "jobs"
LEGACY_TEMP_ROOT = WORKSPACE_ROOT / "temp"


def collect_csvs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.csv") if p.is_file())


def collect_all_csvs() -> list[Path]:
    files = collect_csvs(JOBS_ROOT) + collect_csvs(LEGACY_TEMP_ROOT)
    return sorted({p.resolve() for p in files})


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete CSV files under workspace jobs/ while preserving reports, plans, and non-CSV artifacts.")
    parser.add_argument("--delete", action="store_true", help="Actually delete the matched CSV files. Default is dry-run.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    files = collect_all_csvs()
    rel_paths = [str(p.relative_to(WORKSPACE_ROOT)) for p in files]

    deleted: list[str] = []
    if args.delete:
        for path in files:
            path.unlink(missing_ok=True)
            deleted.append(str(path.relative_to(WORKSPACE_ROOT)))

    summary = {
        "workspace": str(WORKSPACE_ROOT),
        "scope": [str(JOBS_ROOT.relative_to(WORKSPACE_ROOT)), str(LEGACY_TEMP_ROOT.relative_to(WORKSPACE_ROOT))],
        "mode": "delete" if args.delete else "dry-run",
        "matched_count": len(files),
        "deleted_count": len(deleted),
        "matched_files": rel_paths,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if not files:
        print("No CSV files found under jobs/.")
        return

    action = "Deleted" if args.delete else "Would delete"
    print(f"{action} {len(files)} CSV file(s) under jobs/.")
    for rel in rel_paths[:50]:
        print(rel)
    remaining = len(files) - min(len(files), 50)
    if remaining > 0:
        print(f"... and {remaining} more")


if __name__ == "__main__":
    main()
