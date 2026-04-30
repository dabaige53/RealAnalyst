#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = WORKSPACE_DIR / "runtime"
RUNTIME_DB_PATH = RUNTIME_DIR / "registry.db"


def workspace_dir() -> Path:
    return WORKSPACE_DIR


def runtime_dir() -> Path:
    return RUNTIME_DIR


def runtime_db_path() -> Path:
    return RUNTIME_DB_PATH
