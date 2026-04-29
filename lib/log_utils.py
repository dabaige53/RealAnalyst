"""Lightweight logging helpers shared by RealAnalyst scripts.

The scripts intentionally keep stdout machine-readable where possible. Callers that
redirect stdout can persist the collected log lines through ``get_log_file``.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def get_log_file(output_dir: str | Path) -> Path:
    """Return the default log file path for a job/output directory."""
    base = Path(output_dir)
    log_dir = base / ".meta"
    if not log_dir.exists():
        log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "run.log"


def reset_log(output_dir: str | Path) -> None:
    """Reset the default log file if it already exists."""
    path = get_log_file(output_dir)
    path.write_text("", encoding="utf-8")


def log(output_dir: str | Path, stage: str, message: str) -> None:
    """Emit a timestamped line to stdout and append it to the default log file."""
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()
    line = f"[{timestamp}] [{stage}] {message}"
    print(line)
    try:
        with get_log_file(output_dir).open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        # Logging must never break analysis execution.
        pass


@contextmanager
def stage_logger(output_dir: str | Path, stage: str) -> Iterator[None]:
    """Small context manager for future scripts that want stage boundary logs."""
    log(output_dir, stage, "start")
    try:
        yield
    except Exception as exc:
        log(output_dir, stage, f"failed: {exc}")
        raise
    else:
        log(output_dir, stage, "done")
