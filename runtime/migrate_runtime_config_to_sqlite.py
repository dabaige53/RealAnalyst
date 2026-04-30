#!/usr/bin/env python3
"""Bootstrap runtime lookup tables in runtime/registry.db from runtime/*.yaml."""

from __future__ import annotations

import json

from runtime_config_store import db_path, migrate_from_yaml


def main() -> int:
    result = migrate_from_yaml(force=True)
    print(
        json.dumps(
            {
                "success": True,
                "db_path": str(db_path()),
                "result": result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
