#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SPAM_PATTERN = re.compile(r"\bpayment\s+address\b", re.IGNORECASE)
API_BASE = "https://api.github.com"


@dataclass(frozen=True)
class ModerationAction:
    event_name: str
    target_type: str
    target_url: str
    reason: str


def contains_spam(text: str | None) -> bool:
    return bool(text and SPAM_PATTERN.search(text))


def load_event(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub event payload must be a JSON object.")
    return payload


def planned_action(event_name: str, payload: dict[str, Any]) -> ModerationAction | None:
    if event_name == "issue_comment":
        comment = payload.get("comment") or {}
        body = str(comment.get("body") or "")
        url = str(comment.get("url") or "")
        if contains_spam(body) and url:
            return ModerationAction(event_name, "comment", url, "matched Payment Address in issue comment")
        return None

    if event_name == "issues":
        issue = payload.get("issue") or {}
        body = str(issue.get("body") or "")
        url = str(issue.get("url") or "")
        if contains_spam(body) and url:
            return ModerationAction(event_name, "issue", url, "matched Payment Address in issue body")
        return None

    return None


def github_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> None:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - GitHub API URL from event payload
        response.read()


def apply_action(action: ModerationAction, token: str) -> None:
    if action.target_type == "comment":
        github_request("DELETE", action.target_url, token)
        return

    if action.target_type == "issue":
        github_request(
            "PATCH",
            action.target_url,
            token,
            {
                "state": "closed",
                "state_reason": "not_planned",
                "body": "[Removed by automated spam moderation.]",
            },
        )
        return

    raise ValueError(f"Unsupported target type: {action.target_type}")


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Moderate issue spam matching Payment Address.")
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.event_name:
        raise SystemExit("--event-name or GITHUB_EVENT_NAME is required")
    if not args.event_path:
        raise SystemExit("--event-path or GITHUB_EVENT_PATH is required")

    try:
        payload = load_event(Path(args.event_path))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit({"success": False, "error": f"Invalid GitHub event payload: {exc}", "error_code": "EVENT_PAYLOAD_INVALID"})
        return 2
    action = planned_action(args.event_name, payload)
    if action is None:
        emit({"success": True, "action": "none", "event_name": args.event_name})
        return 0

    result: dict[str, Any] = {
        "success": True,
        "action": "planned" if args.dry_run else "applied",
        "event_name": action.event_name,
        "target_type": action.target_type,
        "reason": action.reason,
    }

    if not args.dry_run:
        if not args.token:
            emit({"success": False, "error": "GITHUB_TOKEN is required when not using --dry-run", "error_code": "TOKEN_REQUIRED"})
            return 2
        try:
            apply_action(action, args.token)
        except urllib.error.HTTPError as exc:
            emit({"success": False, "error": f"GitHub API request failed: HTTP {exc.code}", "error_code": "GITHUB_API_FAILED"})
            return 1

    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
