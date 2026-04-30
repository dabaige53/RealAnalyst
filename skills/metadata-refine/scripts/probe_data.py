#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from _common import make_refine_id, now_iso, relpath, resolve_workspace_path, runtime_refine_dir, workspace_path, write_json


def infer_type(values: list[str]) -> str:
    non_empty = [value for value in values if value != ""]
    if not non_empty:
        return "empty"
    numeric = 0
    integer = 0
    for value in non_empty:
        try:
            float(value.replace(",", ""))
            numeric += 1
            if value.replace(",", "").isdigit():
                integer += 1
        except ValueError:
            pass
    ratio = numeric / len(non_empty)
    if ratio >= 0.9:
        return "integer" if integer / len(non_empty) >= 0.9 else "number"
    return "string"


def summarize_csv(path: Path, *, max_rows: int) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("CSV has no header")
        fieldnames = list(reader.fieldnames)
        values: dict[str, list[str]] = {name: [] for name in fieldnames}
        counters: dict[str, Counter[str]] = {name: Counter() for name in fieldnames}
        rows = 0
        for row in reader:
            rows += 1
            if rows > max_rows:
                break
            for name in fieldnames:
                value = (row.get(name) or "").strip()
                values[name].append(value)
                if value:
                    counters[name][value] += 1

    columns: list[dict[str, Any]] = []
    sampled_rows = min(rows, max_rows)
    for name in fieldnames:
        column_values = values[name]
        null_count = sum(1 for value in column_values if value == "")
        non_empty = [value for value in column_values if value != ""]
        top_values = counters[name].most_common(8)
        columns.append(
            {
                "name": name,
                "observed_type": infer_type(column_values),
                "sampled_rows": sampled_rows,
                "null_count": null_count,
                "null_rate": round(null_count / sampled_rows, 6) if sampled_rows else 0,
                "distinct_count_sample": len(counters[name]),
                "sample_values": non_empty[:5],
                "top_values": [{"value": value, "count": count} for value, count in top_values],
            }
        )
    return {"row_sample_count": sampled_rows, "column_count": len(fieldnames), "columns": columns}


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# data probe summary",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- data_csv: {payload['data_csv']}",
        f"- sampled_rows: {payload['probe']['row_sample_count']}",
        f"- column_count: {payload['probe']['column_count']}",
        "",
        "| field | observed_type | null_rate | distinct_sample | sample_values |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for column in payload["probe"]["columns"]:
        samples = ", ".join(str(value) for value in column.get("sample_values", []))
        lines.append(
            f"| {column['name']} | {column['observed_type']} | {column['null_rate']} | {column['distinct_count_sample']} | {samples} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a CSV for metadata refinement evidence.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--refine-id", default="")
    parser.add_argument("--dataset-id", default="")
    parser.add_argument("--data-csv", required=True)
    parser.add_argument("--max-rows", type=int, default=5000)
    args = parser.parse_args()

    workspace = workspace_path(args.workspace)
    data_csv = resolve_workspace_path(workspace, args.data_csv)
    if data_csv is None or not data_csv.exists():
        raise SystemExit(f"data csv not found: {args.data_csv}")
    refine_id = args.refine_id.strip() or make_refine_id(args.session_id or args.dataset_id or data_csv.stem)
    out_dir = runtime_refine_dir(workspace, refine_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "success": True,
        "refine_id": refine_id,
        "job_id": args.session_id.strip(),
        "dataset_id": args.dataset_id.strip(),
        "generated_at": now_iso(),
        "data_csv": relpath(workspace, data_csv),
        "max_rows": args.max_rows,
        "probe": summarize_csv(data_csv, max_rows=args.max_rows),
    }
    write_json(out_dir / "data_probe.json", payload)
    write_summary(out_dir / "data_probe_summary.md", payload)
    print(json.dumps({"success": True, "refine_id": refine_id, "output_dir": str(out_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
