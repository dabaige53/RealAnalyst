#!/usr/bin/env python3
from __future__ import annotations

"""
Tableau Authentication Module

Shared authentication utilities for Tableau REST API.
All credentials are read from environment variables.

Environment Variables:
    TABLEAU_BASE_URL: Tableau Server URL (e.g., https://tableau.example.com)
    TABLEAU_PAT_NAME: Personal Access Token name
    TABLEAU_PAT_SECRET: Personal Access Token secret
    TABLEAU_SITE_ID: Site content URL (optional, defaults to "")
"""

import argparse
import json
import os
import ssl
import sys
from typing import NamedTuple

import requests
from dotenv import find_dotenv, load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# Load .env explicitly for agent context where env vars might be lost
load_dotenv(find_dotenv(usecwd=True))
# Fallback: try loading from project root if running from workspace
load_dotenv(os.path.join(os.getcwd(), "..", ".env"))


class _TLSv12HttpAdapter(HTTPAdapter):
    """Force TLSv1.2 for Tableau endpoints.

    背景：部分企业网络/中间设备对 TLSv1.3 ClientHello 兼容性不稳定，
    会触发 SSLEOFError/UNEXPECTED_EOF_WHILE_READING。对 Tableau 固定 TLSv1.2
    是更稳的工程折中。
    """

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):  # type: ignore[override]
        ctx = ssl.create_default_context()
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            # 兜底：老版本/实现不支持 TLSVersion 时，禁用 TLS1.3
            ctx.options |= getattr(ssl, "OP_NO_TLSv1_3", 0)

        pool_kwargs["ssl_context"] = ctx
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )


def _build_session() -> requests.Session:
    s = requests.Session()
    adapter = _TLSv12HttpAdapter()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class AuthResult(NamedTuple):
    """Authentication result containing token and site info."""

    token: str
    site_id: str
    base_url: str


class TableauAuth:
    """Tableau REST API authentication handler."""

    API_VERSION = "3.19"

    def __init__(self):
        self.base_url = os.environ.get("TABLEAU_BASE_URL", "").rstrip("/")
        self.pat_name = os.environ.get("TABLEAU_PAT_NAME", "")
        self.pat_secret = os.environ.get("TABLEAU_PAT_SECRET", "")
        self.site_content_url = os.environ.get("TABLEAU_SITE_ID", "")

        self._token: str | None = None
        self._site_id: str | None = None

        # 统一使用 session：连接复用 + 重试 + TLS1.2 固定
        self.session: requests.Session = _build_session()

    def validate_env(self) -> list[str]:
        """Validate required environment variables.

        Returns:
            List of missing variable names (empty if all present).
        """
        missing = []
        if not self.base_url:
            missing.append("TABLEAU_BASE_URL")
        if not self.pat_name:
            missing.append("TABLEAU_PAT_NAME")
        if not self.pat_secret:
            missing.append("TABLEAU_PAT_SECRET")
        return missing

    def signin(self) -> AuthResult:
        """Authenticate with Tableau Server using PAT.

        Returns:
            AuthResult with token, site_id, and base_url.

        Raises:
            ValueError: If environment variables are missing.
            requests.HTTPError: If authentication fails.
        """
        missing = self.validate_env()
        if missing:
            raise ValueError(f"缺少环境变量: {', '.join(missing)}")

        auth_url = f"{self.base_url}/api/{self.API_VERSION}/auth/signin"
        payload = {
            "credentials": {
                "personalAccessTokenName": self.pat_name,
                "personalAccessTokenSecret": self.pat_secret,
                "site": {"contentUrl": self.site_content_url},
            }
        }

        print(f"[Tableau] 认证中: {self.base_url}", file=sys.stderr)
        headers = {"Accept": "application/json"}
        resp = self.session.post(auth_url, json=payload, headers=headers, timeout=30)

        if resp.status_code != 200:
            raise requests.HTTPError(f"认证失败 ({resp.status_code}): {resp.text}")

        data = resp.json()
        self._token = data["credentials"]["token"]
        self._site_id = data["credentials"]["site"]["id"]

        print(f"[Tableau] 认证成功, Site ID: {self._site_id}", file=sys.stderr)

        # Assert for type checker - we just set these values
        assert self._token is not None
        assert self._site_id is not None

        return AuthResult(
            token=self._token,
            site_id=self._site_id,
            base_url=self.base_url,
        )

    def signout(self) -> None:
        """Sign out from Tableau Server."""
        if not self._token:
            return

        signout_url = f"{self.base_url}/api/{self.API_VERSION}/auth/signout"
        headers = {"X-Tableau-Auth": self._token}

        try:
            self.session.post(signout_url, headers=headers, timeout=10)
            print("[Tableau] 已登出", file=sys.stderr)
        except requests.RequestException:
            pass  # Ignore signout errors

        self._token = None
        self._site_id = None

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers with authentication token.

        Returns:
            Headers dict with X-Tableau-Auth and Accept: application/json.

        Raises:
            ValueError: If not authenticated.
        """
        if not self._token:
            raise ValueError("未认证，请先调用 signin()")
        return {
            "X-Tableau-Auth": self._token,
            "Accept": "application/json",
        }

    @property
    def api_base(self) -> str:
        """Get the API base URL for the authenticated site."""
        if not self._site_id:
            raise ValueError("未认证，请先调用 signin()")
        return f"{self.base_url}/api/{self.API_VERSION}/sites/{self._site_id}"


def get_auth() -> TableauAuth:
    """Create and return a TableauAuth instance.

    Validates environment variables before returning.

    Returns:
        Configured TableauAuth instance.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    auth = TableauAuth()
    missing = auth.validate_env()
    if missing:
        print(f"[Error] 缺少环境变量: {', '.join(missing)}", file=sys.stderr)
        print("\n请在 .env 文件中配置:", file=sys.stderr)
        print("  TABLEAU_BASE_URL=https://tableau.example.com", file=sys.stderr)
        print("  TABLEAU_PAT_NAME=your-token-name", file=sys.stderr)
        print("  TABLEAU_PAT_SECRET=your-token-secret", file=sys.stderr)
        sys.exit(1)
    return auth


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Tableau authentication configuration")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出认证结果")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        auth = get_auth()
        result = auth.signin()
        payload = {
            "success": True,
            "base_url": result.base_url,
            "site_id": result.site_id,
        }
        auth.signout()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("\n✅ 认证成功!")
            print(f"   Base URL: {result.base_url}")
            print(f"   Site ID:  {result.site_id}")
        return 0
    except Exception as e:
        payload = {"success": False, "error": str(e)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"\n❌ 认证失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
