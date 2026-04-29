#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip
python -m pip install -r requirements.txt

python - <<'PY'
import sys
mods = [
  ('requests', None),
  ('dotenv', 'python-dotenv'),
  ('yaml', 'PyYAML'),
  ('numpy', None),
  ('pandas', None),
  ('duckdb', None),
]
missing = []
for m, pkg in mods:
    try:
        __import__(m)
    except Exception:
        missing.append(pkg or m)

if missing:
    raise SystemExit(f"Missing modules after install: {missing}")
print('OK: venv ready:', sys.executable)
PY
