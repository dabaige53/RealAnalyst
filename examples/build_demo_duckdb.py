#!/usr/bin/env python3
"""Build the local demo DuckDB database from examples/data/*.csv."""

from __future__ import annotations

from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = WORKSPACE_DIR / "examples" / "data"
DB_PATH = DATA_DIR / "demo_retail.duckdb"


def main() -> int:
    try:
        import duckdb
    except ModuleNotFoundError as exc:
        raise SystemExit("duckdb is required. Install dependencies with: pip install -r requirements.txt") from exc

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        con.execute("DROP TABLE IF EXISTS orders")
        con.execute("DROP TABLE IF EXISTS forecast")
        con.execute(
            """
            CREATE TABLE orders AS
            SELECT * FROM read_csv_auto(?, HEADER = TRUE)
            """,
            [str(DATA_DIR / "retail_orders.csv")],
        )
        con.execute(
            """
            CREATE TABLE forecast AS
            SELECT * FROM read_csv_auto(?, HEADER = TRUE)
            """,
            [str(DATA_DIR / "retail_forecast.csv")],
        )
    finally:
        con.close()

    print(f"created {DB_PATH.relative_to(WORKSPACE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
