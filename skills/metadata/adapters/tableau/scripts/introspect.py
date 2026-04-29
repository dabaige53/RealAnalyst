#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import requests
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_tableau_scripts_path

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()

from auth import get_auth  # type: ignore[import-not-found]


def introspect_schema() -> dict[str, Any]:
    auth = get_auth()
    auth.signin()

    try:
        query = """
        {
          __schema {
            queryType {
              fields {
                name
              }
            }
          }
        }
        """

        endpoint = f"{auth.base_url}/api/metadata/graphql"
        headers = auth.get_headers()

        resp = requests.post(endpoint, json={"query": query}, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()
    finally:
        auth.signout()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Tableau Metadata API query schema")
    parser.add_argument("--output", help="将返回的 JSON 写入文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = introspect_schema()
    content = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
