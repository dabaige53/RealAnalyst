#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
if str(SQL_DIR) not in sys.path:
    sys.path.insert(0, str(SQL_DIR))

import export_with_meta  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(export_with_meta.main("mysql"))
