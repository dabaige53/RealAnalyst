#!/usr/bin/env python3
"""Test registered SQLite-backed Tableau views with filters."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_tableau_scripts_path, bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_by_entry_key

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()
from auth import get_auth  # noqa: E402  # type: ignore[import-not-found]

TEST_OUTPUT_DIR = WORKSPACE_DIR / "jobs" / "test_views"


def export_view_data(auth, view_luid: str, filters: dict[str, Any] | None = None) -> tuple[int, str]:
    filter_params = ""
    if filters:
        params = []
        for field, value in filters.items():
            encoded_field = urllib.parse.quote(field, safe="")
            encoded_value = urllib.parse.quote(str(value), safe="")
            params.append(f"vf_{encoded_field}={encoded_value}")
        if params:
            filter_params = "?" + "&".join(params)

    data_url = f"{auth.api_base}/views/{view_luid}/data{filter_params}"
    resp = auth.session.get(data_url, headers=auth.get_headers(), timeout=120)
    if resp.status_code != 200:
        raise Exception(f"Export failed: {resp.status_code} - {resp.text[:200]}")

    csv_content = resp.content.decode("utf-8", errors="ignore")
    lines = csv_content.strip().split("\n")
    row_count = len(lines) - 1 if len(lines) > 1 else 0
    return row_count, csv_content


def pick_test_filter(entry_key: str) -> tuple[str, str] | None:
    spec = load_spec_by_entry_key(entry_key) or {}
    filters = spec.get("filters", [])
    skip_fields = {"度量名称", "度量值", "Measure Names", "Measure Values"}
    if not isinstance(filters, list):
        return None

    for f in filters:
        if not isinstance(f, dict):
            continue
        field_name = f.get("tableau_field", "")
        if field_name in skip_fields:
            continue
        sample_values = f.get("sample_values", [])
        if not isinstance(sample_values, list):
            continue
        for val in sample_values:
            if isinstance(val, str) and val.strip():
                return field_name, val
    return None


def test_single_view(auth, entry: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    key = entry.get("key")
    view_luid = entry.get("tableau", {}).get("view_luid")
    display_name = entry.get("display_name", key)

    result: dict[str, Any] = {
        "key": key,
        "display_name": display_name,
        "view_luid": view_luid,
        "baseline": None,
        "filtered": None,
        "filter_used": None,
        "success": False,
        "error": None,
    }

    try:
        safe_key = str(key).replace(".", "_") if key else "unknown"
        view_dir = output_dir / safe_key
        view_dir.mkdir(parents=True, exist_ok=True)

        print("  [1/2] Baseline export...")
        baseline_rows, baseline_csv = export_view_data(auth, str(view_luid))
        (view_dir / "baseline.csv").write_text(baseline_csv, encoding="utf-8")
        result["baseline"] = {"rows": baseline_rows}
        print(f"        → {baseline_rows} rows")

        test_filter = pick_test_filter(str(key))
        if not test_filter:
            result["error"] = "No suitable filter found"
            result["success"] = True
            return result

        filter_field, filter_value = test_filter
        result["filter_used"] = {"field": filter_field, "value": filter_value}

        print(f"  [2/2] Filtered export: {filter_field}={filter_value}")
        filtered_rows, filtered_csv = export_view_data(auth, str(view_luid), {filter_field: filter_value})
        (view_dir / "filtered.csv").write_text(filtered_csv, encoding="utf-8")
        result["filtered"] = {"rows": filtered_rows}
        print(f"        → {filtered_rows} rows")

        if filtered_rows < baseline_rows:
            result["success"] = True
            print(f"  [OK] Filter reduced rows: {baseline_rows} → {filtered_rows}")
        elif filtered_rows == baseline_rows and filtered_rows > 0:
            result["success"] = True
            print("  [WARN] Filter matched all rows (no reduction)")
        else:
            result["error"] = "Filter had no effect or unexpected result"
            print(f"  [FAIL] {result['error']}")

    except Exception as e:
        result["error"] = str(e)
        print(f"  [ERROR] {e}")

    return result


def test_all_views(single_key: str | None = None) -> list[dict[str, Any]]:
    ensure_store_ready()
    entries = [e for e in list_entries(active_only=True) if isinstance(e, dict)]

    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True)

    auth = get_auth()
    auth.signin()
    results: list[dict[str, Any]] = []

    try:
        for entry in entries:
            key = entry.get("key")
            if single_key and key != single_key:
                continue
            view_luid = entry.get("tableau", {}).get("view_luid")
            if not view_luid:
                print(f"[SKIP] {key} (no view_luid)")
                continue

            print(f"\n[TEST] {key}")
            print(f"       {entry.get('display_name', '')}")
            print("-" * 50)
            results.append(test_single_view(auth, entry, TEST_OUTPUT_DIR))

    finally:
        auth.signout()

    summary_path = TEST_OUTPUT_DIR / "test_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "total": len(results),
                "passed": sum(1 for r in results if r["success"]),
                "failed": sum(1 for r in results if not r["success"]),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Tableau views with filters")
    parser.add_argument("--key", help="Test single view by key")
    args = parser.parse_args()

    print("=" * 60)
    print("Tableau View Export Test (with Filters)")
    print("=" * 60)
    print(f"Output: {TEST_OUTPUT_DIR}")

    results = test_all_views(single_key=args.key)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])

    print(f"Total:  {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    print("\nDetails:")
    for r in results:
        status = "✅" if r["success"] else "❌"
        baseline = r.get("baseline", {}).get("rows", "?") if r.get("baseline") else "?"
        filtered = r.get("filtered", {}).get("rows", "-") if r.get("filtered") else "-"
        filter_info = ""
        if r.get("filter_used"):
            f = r["filter_used"]
            filter_info = f" | filter: {f['field']}={str(f['value'])[:20]}"
        print(f"  {status} {r['key']}: {baseline} → {filtered}{filter_info}")
        if r.get("error") and not r["success"]:
            print(f"     Error: {r['error']}")


if __name__ == "__main__":
    main()
