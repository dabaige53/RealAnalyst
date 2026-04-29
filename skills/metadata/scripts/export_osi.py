#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_io import (
    iter_dataset_files,
    iter_dictionary_files,
    iter_mapping_files,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
)
from skills.metadata.lib.metadata_osi import build_osi_model


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _ref_ids(values) -> set[str]:
    refs: set[str] = set()
    for value in _as_list(values):
        if isinstance(value, str):
            refs.add(value)
        elif isinstance(value, dict):
            refs.add(str(value.get("id") or value.get("dictionary_id") or ""))
    return {ref for ref in refs if ref}


def _enrich_dataset(dataset: dict, dictionaries: list[dict], mappings: list[dict]) -> dict:
    refs = _ref_ids(dataset.get("dictionary_refs"))
    metrics = list(_as_list(dataset.get("metrics")))
    metric_names = {metric.get("name") for metric in metrics if isinstance(metric, dict)}
    for dictionary in dictionaries:
        if dictionary.get("id") not in refs:
            continue
        for metric in _as_list(dictionary.get("metrics")):
            if isinstance(metric, dict) and metric.get("name") not in metric_names:
                metrics.append(metric)
                metric_names.add(metric.get("name"))
    enriched = dict(dataset)
    enriched["metrics"] = metrics
    enriched["mappings"] = [
        mapping
        for mapping in mappings
        if mapping.get("id") == dataset.get("mapping_ref") or mapping.get("source_id") == dataset.get("id")
    ]
    return enriched


def main() -> int:
    parser = argparse.ArgumentParser(description="Export metadata YAML into OSI semantic model YAML.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else workspace / "metadata" / "osi" / f"{args.model_name}.osi.yaml"
    )

    dictionaries = [load_mapping_file(path) for path in iter_dictionary_files(workspace)]
    mappings = [load_mapping_file(path) for path in iter_mapping_files(workspace)]
    datasets = [
        _enrich_dataset(normalize_dataset(load_dataset_file(path), path=path), dictionaries, mappings)
        for path in iter_dataset_files(workspace)
    ]
    payload = build_osi_model(args.model_name, datasets)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "success": True,
                "model_name": args.model_name,
                "output": str(output_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
