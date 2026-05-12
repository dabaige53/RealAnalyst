#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_API = "https://api.github.com/repos/dabaige53/RealAnalyst"


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed GitHub API URL
        return json.loads(response.read().decode("utf-8"))


def plugin_version(repo: Path) -> str:
    payload = json.loads((repo / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return str(payload.get("version") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check plugin version, latest tag, and latest GitHub Release alignment.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--allow-network-failure", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    version = plugin_version(repo)
    expected_tag = f"v{version}" if version and not version.startswith("v") else version
    payload: dict[str, Any] = {"plugin_version": version, "expected_tag": expected_tag}

    try:
        tags = fetch_json(f"{REPO_API}/tags")
        latest_release = fetch_json(f"{REPO_API}/releases/latest")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        payload.update({"success": bool(args.allow_network_failure), "warning": f"GitHub API unavailable: {exc}"})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if args.allow_network_failure else 1

    tag_names = {str((t or {}).get("name") or "") for t in tags} if isinstance(tags, list) else set()
    latest_release_tag = str(latest_release.get("tag_name") or "") if isinstance(latest_release, dict) else ""
    errors = []
    if expected_tag and expected_tag not in tag_names:
        errors.append(f"expected tag {expected_tag!r} not found in repository tags (found {len(tag_names)} tags)")
    if latest_release_tag != expected_tag:
        errors.append(f"latest release {latest_release_tag!r} does not match plugin version tag {expected_tag!r}")

    payload.update(
        {
            "success": not errors,
            "tag_count": len(tag_names),
            "latest_release_tag": latest_release_tag,
            "errors": errors,
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
