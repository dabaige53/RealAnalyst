#!/usr/bin/env python3
"""Sync field metadata (dimensions/measures) into SQLite-backed per-source specs."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Any

from _bootstrap import bootstrap_tableau_scripts_path, bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_by_entry_key, save_spec
from skills.metadata.lib.value_patterns import compact_sample_values, validation_from_samples

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()
import requests
from auth import TableauAuth, get_auth  # noqa: E402  # type: ignore[import-not-found]

SKIP_FIELDS = {
    "度量名称",
    "度量值",
    "Measure Names",
    "Measure Values",
    "Number of Records",
}


def is_technical_name(name: str) -> bool:
    return name.endswith("校验列") or name.endswith("_标识") or name == "出票日期筛选"


DATA_TYPE_MAP = {
    "STRING": "string",
    "INTEGER": "integer",
    "REAL": "real",
    "DATE": "date",
    "DATETIME": "datetime",
    "BOOLEAN": "boolean",
}


def fetch_sheet_fields(auth: TableauAuth, view_luid: str) -> tuple[list[dict[str, Any]], set[str]]:
    query = """
    query GetSheetFields($luid: String!) {
      sheets(filter: {luid: $luid}) {
        name
        sheetFieldInstances { name }
        datasourceFields {
          name
          __typename
          description
          ... on ColumnField {
            dataType
            role
            dataCategory
          }
          ... on CalculatedField {
            dataType
            role
          }
          ... on DatasourceField {
            upstreamFields {
              name
              __typename
              ... on ColumnField {
                dataType
                role
              }
            }
          }
        }
      }
    }
    """

    endpoint = f"{auth.base_url}/api/metadata/graphql"
    headers = auth.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        resp = auth.session.post(
            endpoint,
            json={"query": query, "variables": {"luid": view_luid}},
            headers=headers,
            timeout=60,
        )

        if resp.status_code != 200:
            print(f"  [WARN] Metadata API returned {resp.status_code}", file=sys.stderr)
            return ([], set())

        data = resp.json()
        if "errors" in data:
            print(
                f"  [WARN] GraphQL errors: {data['errors'][0].get('message', '')}",
                file=sys.stderr,
            )
            return ([], set())

        sheets = data.get("data", {}).get("sheets", [])
        if not sheets:
            return ([], set())

        sheet = sheets[0]
        visible_names = {
            name
            for f in (sheet.get("sheetFieldInstances") or [])
            if isinstance(f, dict)
            for name in [f.get("name")]
            if isinstance(name, str) and name
        }
        return (sheet.get("datasourceFields", []) or [], visible_names)

    except Exception as e:
        print(f"  [ERROR] Failed to fetch fields: {e}", file=sys.stderr)
        return ([], set())


def fetch_workbook_fields(
    auth: TableauAuth, workbook_luid: str
) -> tuple[list[dict[str, Any]], set[str]]:
    query = """
    query GetWorkbookFields($luid: String!) {
      workbooks(filter: {luid: $luid}) {
        name
        sheets {
          name
          luid
          sheetFieldInstances { name }
          datasourceFields {
            name
            __typename
            description
            ... on ColumnField {
              dataType
              role
            }
            ... on CalculatedField {
              dataType
              role
            }
          }
        }
      }
    }
    """

    endpoint = f"{auth.base_url}/api/metadata/graphql"
    headers = auth.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        resp = auth.session.post(
            endpoint,
            json={"query": query, "variables": {"luid": workbook_luid}},
            headers=headers,
            timeout=60,
        )

        if resp.status_code != 200:
            return ([], set())

        data = resp.json()
        if "errors" in data:
            return ([], set())

        workbooks = data.get("data", {}).get("workbooks", [])
        if not workbooks:
            return ([], set())

        all_fields: list[dict[str, Any]] = []
        seen: set[str] = set()
        visible_all: set[str] = set()
        for sheet in workbooks[0].get("sheets", []):
            visible = {
                name
                for f in (sheet.get("sheetFieldInstances") or [])
                if isinstance(f, dict)
                for name in [f.get("name")]
                if isinstance(name, str) and name
            }
            visible_all |= visible
            for field in sheet.get("datasourceFields", []):
                name = field.get("name", "")
                if not name or name in seen:
                    continue
                if visible and name not in visible:
                    continue
                seen.add(name)
                all_fields.append(field)

        return (all_fields, visible_all)

    except Exception as e:
        print(f"  [ERROR] Failed to fetch workbook fields: {e}", file=sys.stderr)
        return ([], set())


def get_workbook_luid(auth: TableauAuth, view_luid: str) -> str | None:
    try:
        url = f"{auth.api_base}/views/{view_luid}"
        resp = auth.session.get(url, headers=auth.get_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("view", {}).get("workbook", {}).get("id")
    except Exception:
        pass
    return None


def fetch_sample_values(
    auth: TableauAuth, view_luid: str, dimension_names: list[str]
) -> dict[str, list[str]]:
    import csv
    from io import StringIO

    url = f"{auth.api_base}/views/{view_luid}/data?maxAge=1"
    try:
        resp = auth.session.get(url, headers=auth.get_headers(), timeout=120)
        if resp.status_code != 200:
            print(f"  [WARN] CSV export returned {resp.status_code}", file=sys.stderr)
            return {}

        content = resp.content.decode("utf-8", errors="ignore")
        reader = csv.reader(StringIO(content))
        headers = next(reader, [])

        dim_indices = {name: idx for idx, name in enumerate(headers) if name in dimension_names}
        if not dim_indices:
            return {}

        samples: dict[str, set[str]] = {name: set() for name in dim_indices}
        for i, row in enumerate(reader):
            if i >= 200:
                break
            for name, idx in dim_indices.items():
                if idx < len(row) and row[idx].strip():
                    samples[name].add(row[idx].strip())

        return {name: compact_sample_values(sorted(values), limit=20) for name, values in samples.items() if values}

    except Exception as e:
        print(f"  [WARN] Failed to fetch sample values: {e}", file=sys.stderr)
        return {}


def process_fields(
    raw_fields: list[dict[str, Any]], visible_names: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dimensions: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []
    seen = set()

    for field in raw_fields:
        name = field.get("name", "")
        if not name or name in seen or name in SKIP_FIELDS or name.startswith(":"):
            continue
        if is_technical_name(name):
            continue
        if visible_names and name not in visible_names:
            continue

        seen.add(name)
        role = field.get("role") or ""
        raw_data_type = field.get("dataType") or ""
        typename = field.get("__typename", "")

        if typename == "DatasourceField" and not role:
            upstream = field.get("upstreamFields") or []
            if upstream and isinstance(upstream, list):
                upstream_field = upstream[0]
                role = upstream_field.get("role") or ""
                raw_data_type = upstream_field.get("dataType") or raw_data_type

        data_type = DATA_TYPE_MAP.get(raw_data_type, "string")
        entry: dict[str, Any] = {"name": name, "data_type": data_type}
        if field.get("description"):
            entry["description"] = field["description"]

        if role == "MEASURE":
            measures.append(entry)
        elif role == "DIMENSION":
            dimensions.append(entry)
        elif raw_data_type in ("INTEGER", "REAL"):
            measures.append(entry)
        else:
            dimensions.append(entry)

    dimensions.sort(key=lambda x: x["name"])
    measures.sort(key=lambda x: x["name"])
    return dimensions, measures


def merge_field_lists(
    existing: list[dict[str, Any]], fetched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing_by_name = {f.get("name"): f for f in existing}
    result = []

    for fetched_field in fetched:
        name = fetched_field.get("name")
        if name in existing_by_name:
            merged = {**fetched_field}
            existing_field = existing_by_name[name]
            if existing_field.get("description"):
                merged["description"] = existing_field["description"]
            if existing_field.get("validation"):
                merged["validation"] = existing_field["validation"]
            if existing_field.get("sample_values"):
                existing_samples = set(existing_field.get("sample_values", []))
                fetched_samples = set(fetched_field.get("sample_values", []))
                merged_samples = sorted(existing_samples | fetched_samples)
                merged["sample_values"] = compact_sample_values(merged_samples, limit=20)
                if not merged.get("validation"):
                    validation = validation_from_samples(merged_samples)
                    if validation:
                        merged["validation"] = validation
            result.append(merged)
        else:
            result.append(fetched_field)

    return result


def get_spec_fields(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dims = spec.get("dimensions", [])
    meas = spec.get("measures", [])
    dims_dicts = [d for d in dims if isinstance(d, dict)] if isinstance(dims, list) else []
    meas_dicts = [m for m in meas if isinstance(m, dict)] if isinstance(meas, list) else []
    return dims_dicts, meas_dicts


def sync_entry(
    auth: TableauAuth, entry: dict[str, Any], dry_run: bool = False, with_samples: bool = False
) -> dict[str, Any]:
    key = entry.get("key", "")
    entry_type = entry.get("type", "view")

    if entry_type == "domain":
        views = entry.get("views", [])
        view_luid = views[0].get("view_luid") if views else None
        workbook_luid = entry.get("tableau", {}).get("workbook_id")
    else:
        view_luid = entry.get("tableau", {}).get("view_luid")
        workbook_luid = entry.get("tableau", {}).get("workbook_id")

    if not view_luid and not workbook_luid:
        return {"status": "skipped", "reason": "no view_luid or workbook_id"}

    print(f"[SYNC] {key}")

    raw_fields: list[dict[str, Any]] = []
    visible_names: set[str] = set()

    if view_luid:
        print(f"  Fetching sheet fields (view_luid: {str(view_luid)[:8]}...)")
        raw_fields, visible_names = fetch_sheet_fields(auth, str(view_luid))

    if not raw_fields and workbook_luid:
        print(f"  Fallback: fetching workbook fields (workbook_id: {str(workbook_luid)[:8]}...)")
        raw_fields, visible_names = fetch_workbook_fields(auth, str(workbook_luid))

    if not raw_fields and view_luid:
        wb_luid = get_workbook_luid(auth, str(view_luid))
        if wb_luid:
            print(f"  Fallback: fetching via workbook (discovered: {wb_luid[:8]}...)")
            raw_fields, visible_names = fetch_workbook_fields(auth, wb_luid)

    if not raw_fields:
        print("  [WARN] No fields found")
        return {"status": "empty", "count": 0}

    fetched_dims, fetched_meas = process_fields(raw_fields, visible_names)

    if with_samples and view_luid and fetched_dims:
        print("  Fetching sample values...")
        dim_names = [d["name"] for d in fetched_dims]
        samples = fetch_sample_values(auth, str(view_luid), dim_names)
        for dim in fetched_dims:
            if dim["name"] in samples:
                dim["sample_values"] = samples[dim["name"]]
                validation = validation_from_samples(samples[dim["name"]])
                if validation:
                    dim["validation"] = validation
        print(f"  Got samples for {len(samples)}/{len(dim_names)} dimensions")

    spec = load_spec_by_entry_key(str(key)) or {}
    existing_dims, existing_meas = get_spec_fields(spec)
    merged_dims = merge_field_lists(existing_dims, fetched_dims)
    merged_meas = merge_field_lists(existing_meas, fetched_meas)

    print(f"  Dimensions: {len(fetched_dims)} fetched, {len(merged_dims)} after merge")
    print(f"  Measures: {len(fetched_meas)} fetched, {len(merged_meas)} after merge")

    if dry_run:
        return {
            "status": "synced",
            "dimensions": len(merged_dims),
            "measures": len(merged_meas),
            "dry_run": True,
        }

    spec["entry_key"] = key
    spec.setdefault("display_name", entry.get("display_name", key))
    spec["updated"] = datetime.now().strftime("%Y-%m-%d")
    spec["dimensions"] = merged_dims
    spec["measures"] = merged_meas
    save_spec(spec)
    print(f"  [SAVED] spec -> registry.db::{key}")

    return {
        "status": "synced",
        "dimensions": len(merged_dims),
        "measures": len(merged_meas),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync field metadata from Tableau via GraphQL")
    parser.add_argument("--key", help="Sync specific entry by key")
    parser.add_argument("--all", action="store_true", help="Sync all active entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument(
        "--with-samples", action="store_true", help="Fetch sample values for dimensions"
    )
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        sys.exit(1)

    ensure_store_ready()
    if args.key:
        entries = [e for e in list_entries(active_only=False) if isinstance(e, dict) and e.get("key") == args.key]
        if not entries:
            print(f"[Error] Entry '{args.key}' not found", file=sys.stderr)
            sys.exit(1)
    else:
        entries = [e for e in list_entries(active_only=True) if isinstance(e, dict)]

    print("=" * 60)
    print("Tableau Field Sync (Metadata API)")
    print("=" * 60)
    print("[MODE] Dry-run\n" if args.dry_run else "[MODE] Live\n")

    auth = get_auth()
    auth.signin()

    results = {"synced": 0, "empty": 0, "skipped": 0}
    try:
        for entry in entries:
            result = sync_entry(auth, entry, dry_run=args.dry_run, with_samples=args.with_samples)
            status = result.get("status", "skipped")
            results[status] = results.get(status, 0) + 1
    finally:
        auth.signout()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Synced:  {results['synced']}")
    print(f"Empty:   {results['empty']}")
    print(f"Skipped: {results['skipped']}")
    print(f"\nUpdated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
