#!/usr/bin/env python3
"""Generate a safe SESSION_ID / job id for jobs/<SESSION_ID>/.

Why:
- Many tools write to jobs/{SESSION_ID}/ and expect the id to be set.
- This helper creates a deterministic, filesystem-safe id.

Usage:
  python3 skills/analysis-run/scripts/new_session_id.py
  python3 skills/analysis-run/scripts/new_session_id.py --prefix discord
  python3 skills/analysis-run/scripts/new_session_id.py --prefix discord --hint 1483721617774477312

Output:
  Prints the id to stdout.
"""

from __future__ import annotations

import argparse
import secrets
from datetime import datetime, timezone


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a safe SESSION_ID for jobs/<SESSION_ID>/")
    ap.add_argument("--prefix", default="job", help="Prefix for the id (default: job)")
    ap.add_argument(
        "--hint",
        default="",
        help="Optional hint to embed (e.g., message_id). Will be sanitized.",
    )
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)

    prefix = "".join(ch for ch in str(args.prefix).strip() if ch.isalnum() or ch in "-_") or "job"
    hint = "".join(ch for ch in str(args.hint).strip() if ch.isalnum() or ch in "-_")

    parts = [prefix, ts]
    if hint:
        parts.append(hint[:32])
    parts.append(rand)

    print("-".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
