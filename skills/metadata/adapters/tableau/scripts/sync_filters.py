#!/usr/bin/env python3
"""Sync per-view filters and parameters into SQLite-backed per-source specs."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from io import StringIO
from typing import Any

from _bootstrap import bootstrap_tableau_scripts_path, bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_by_entry_key, save_spec
from skills.metadata.lib.value_patterns import compact_sample_values, validation_from_samples

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()
from auth import TableauAuth, get_auth  # noqa: E402  # type: ignore[import-not-found]


def is_technical_name(name: str) -> bool:
    return (
        name.startswith(":")
        or name.endswith("校验列")
        or name.endswith("_标识")
        or name == "出票日期筛选"
    )


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]


def fetch_sheet_meta(auth: TableauAuth, view_luid: str) -> dict[str, Any] | None:
    query = """
    query GetSheetMeta($luid: String!) {
      sheets(filter: {luid: $luid}) {
        name
        workbook { parameters { name } }
        sheetFieldInstances { name }
        datasourceFields {
          name
          __typename
          description
          ... on ColumnField { role }
          ... on CalculatedField { role formula parameters { name } }
        }
      }
    }
    """

    endpoint = f"{auth.base_url}/api/metadata/graphql"
    headers = auth.get_headers()
    headers["Content-Type"] = "application/json"

    resp = auth.session.post(
        endpoint,
        json={"query": query, "variables": {"luid": view_luid}},
        headers=headers,
        timeout=60,
    )
    if resp.status_code != 200:
        return None

    data = resp.json()
    if data.get("errors"):
        return None

    sheets = (data.get("data") or {}).get("sheets") or []
    if not sheets:
        return None

    sheet = sheets[0]
    used_fields = {f.get("name") for f in (sheet.get("sheetFieldInstances") or []) if f.get("name")}
    ds_fields = sheet.get("datasourceFields") or []
    wb_params = (sheet.get("workbook") or {}).get("parameters") or []
    wb_param_names = [p.get("name") for p in wb_params if isinstance(p, dict) and p.get("name")]

    return {
        "sheet_name": sheet.get("name"),
        "used_fields": used_fields,
        "datasource_fields": ds_fields,
        "workbook_param_names": wb_param_names,
    }


def _extract_used_param_names(
    workbook_param_names: list[str], datasource_fields: list[dict[str, Any]], used_fields: set[str]
) -> list[str]:
    workbook_param_set = set(workbook_param_names)
    used_param_set: set[str] = set()

    bracket_token_re = re.compile(r"\[([^\]]+)\]")

    for f in datasource_fields:
        name = f.get("name")
        if not isinstance(name, str) or name not in used_fields:
            continue
        if f.get("__typename") != "CalculatedField":
            continue

        for p in f.get("parameters") or []:
            if isinstance(p, dict) and p.get("name"):
                used_param_set.add(p["name"])

        formula = f.get("formula")
        if isinstance(formula, str) and formula:
            for token in bracket_token_re.findall(formula):
                if token in workbook_param_set:
                    used_param_set.add(token)

    used_param_set = {p for p in used_param_set if p in workbook_param_set}
    return [p for p in workbook_param_names if p in used_param_set]


def build_filters(meta: dict[str, Any]) -> list[dict[str, Any]]:
    used_fields: set[str] = meta["used_fields"]
    ds_fields: list[dict[str, Any]] = meta["datasource_fields"]

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in ds_fields:
        name = f.get("name")
        if not isinstance(name, str) or not name:
            continue
        if name in seen or name not in used_fields or is_technical_name(name):
            continue
        if f.get("role") == "MEASURE":
            continue

        seen.add(name)
        results.append({"tableau_field": name})

    results.sort(key=lambda x: x["tableau_field"])
    return results


def build_parameters(meta: dict[str, Any]) -> list[dict[str, Any]]:
    used_fields: set[str] = meta["used_fields"]
    ds_fields: list[dict[str, Any]] = meta["datasource_fields"]
    wb_param_names: list[str] = meta["workbook_param_names"]

    used_param_names = _extract_used_param_names(wb_param_names, ds_fields, used_fields)
    return [{"tableau_field": p} for p in used_param_names]


def fetch_sample_values(
    auth: TableauAuth, view_luid: str, display_names: list[str]
) -> dict[str, list[str]]:
    url = f"{auth.api_base}/views/{view_luid}/data?maxAge=1"
    resp = auth.session.get(url, headers=auth.get_headers(), timeout=120)
    if resp.status_code != 200:
        return {}

    content = resp.content.decode("utf-8", errors="ignore")
    reader = csv.reader(StringIO(content))
    headers = next(reader, [])

    indices = {name: idx for idx, name in enumerate(headers) if name in display_names}
    if not indices:
        return {}

    samples: dict[str, set[str]] = {name: set() for name in indices}
    for i, row in enumerate(reader):
        if i >= 500:
            break
        for name, idx in indices.items():
            if idx < len(row):
                v = row[idx].strip()
                if v:
                    samples[name].add(v)

    return {name: compact_sample_values(sorted(values), limit=50) for name, values in samples.items() if values}


def merge_items(
    existing: list[dict[str, Any]], fetched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing_by_field = {i.get("tableau_field"): i for i in existing if isinstance(i, dict)}
    preserve = {"sample_values", "validation", "key", "display_name", "kind", "apply_via", "in_view"}
    out: list[dict[str, Any]] = []
    for item in fetched:
        field = item.get("tableau_field")
        if field in existing_by_field:
            old = existing_by_field[field]
            merged = dict(item)
            for k in preserve:
                if k in old and old.get(k) not in (None, "", [], {}):
                    merged[k] = old[k]
            if merged.get("sample_values"):
                existing_samples = old.get("sample_values") if isinstance(old.get("sample_values"), list) else []
                fetched_samples = item.get("sample_values") if isinstance(item.get("sample_values"), list) else []
                merged_samples = sorted({str(x) for x in [*existing_samples, *fetched_samples] if str(x).strip()})
                merged["sample_values"] = compact_sample_values(merged_samples, limit=50)
                if not merged.get("validation"):
                    validation = validation_from_samples(merged_samples)
                    if validation:
                        merged["validation"] = validation
            out.append(merged)
        else:
            out.append(item)
    return out


def sync_entry(
    auth: TableauAuth, entry: dict[str, Any], dry_run: bool, with_samples: bool
) -> dict[str, Any]:
    key = entry.get("key", "")
    display_name = entry.get("display_name", key)
    entry_type = entry.get("type", "view")

    if entry_type == "domain":
        views = entry.get("views", [])
        view_luid = views[0].get("view_luid") if views else None
    else:
        view_luid = (entry.get("tableau") or {}).get("view_luid")

    if not view_luid:
        return {"status": "skipped", "reason": "no view_luid"}

    meta = fetch_sheet_meta(auth, view_luid)
    if not meta:
        return {"status": "empty"}

    fetched_filters = build_filters(meta)
    fetched_parameters = build_parameters(meta)

    if with_samples and fetched_filters:
        display_names = [f["tableau_field"] for f in fetched_filters]
        samples = fetch_sample_values(auth, view_luid, display_names)
        for f in fetched_filters:
            if f["tableau_field"] in samples:
                f["sample_values"] = samples[f["tableau_field"]]
                validation = validation_from_samples(samples[f["tableau_field"]])
                if validation:
                    f["validation"] = validation

    base = load_spec_by_entry_key(str(key)) or {}
    existing_filters = _as_list_of_dicts(base.get("filters"))
    existing_parameters = _as_list_of_dicts(base.get("parameters"))

    merged_filters = (
        merge_items(existing_filters, fetched_filters) if fetched_filters else existing_filters
    )
    merged_parameters = (
        merge_items(existing_parameters, fetched_parameters)
        if fetched_parameters
        else existing_parameters
    )

    if dry_run:
        return {
            "status": "dry",
            "filters": len(merged_filters),
            "parameters": len(merged_parameters),
        }

    data = dict(base) if isinstance(base, dict) else {}
    data.setdefault("entry_key", key)
    data.setdefault("display_name", display_name)
    data["updated"] = datetime.now().strftime("%Y-%m-%d")
    data["filters"] = merged_filters
    data["parameters"] = merged_parameters
    save_spec(data)

    return {
        "status": "synced",
        "filters": len(merged_filters),
        "parameters": len(merged_parameters),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Tableau filters/parameters into SQLite-backed per-source specs"
    )
    parser.add_argument("--key", help="Sync specific entry by key")
    parser.add_argument("--source-key", dest="key", help="Alias for --key")
    parser.add_argument("--all", action="store_true", help="Sync all active entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument(
        "--with-samples", action="store_true", help="Fetch sample_values for filters"
    )
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        raise SystemExit(2)

    ensure_store_ready()
    if args.key:
        entries = [e for e in list_entries(active_only=False) if isinstance(e, dict) and e.get("key") == args.key]
    else:
        entries = [e for e in list_entries(active_only=True) if isinstance(e, dict)]

    if not entries:
        print("[WARN] No entries matched", file=sys.stderr)
        return

    auth = get_auth()
    auth.signin()
    try:
        for entry in entries:
            k = entry.get("key")
            print(f"[SYNC] {k}")
            res = sync_entry(auth, entry, dry_run=args.dry_run, with_samples=args.with_samples)
            if res.get("status") == "synced":
                print(f"  [OK] filters={res.get('filters')} parameters={res.get('parameters')}")
            elif res.get("status") == "dry":
                print(f"  [DRY] filters={res.get('filters')} parameters={res.get('parameters')}")
            else:
                print(f"  [{res.get('status', 'skipped').upper()}] {res.get('reason', '')}")
    finally:
        auth.signout()


if __name__ == "__main__":
    main()
