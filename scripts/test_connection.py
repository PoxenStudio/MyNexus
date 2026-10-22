#!/usr/bin/env python3
"""
Check connectivity and API token against a running MyNexus instance.
Example:
  python test_connection.py --host http://127.0.0.1:8080 --token mnx_xxx
  MYNEXUS_API_TOKEN=mnx_xxx python test_connection.py --host http://127.0.0.1:8080

It performs two requests:
  1. GET /healthz                 (public)  -> the service is reachable
  2. GET /api/v1/system/health    (auth)    -> the API token is accepted
Both response bodies are printed, and the exit code is non-zero on failure.
"""

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def normalize_host(value: str) -> tuple[str, str]:
    """Return (root_url, api_prefix), accepting either http://host:port or .../api/v1."""
    root = value.rstrip("/")
    prefix = "/api/v1"
    if root.endswith(prefix):
        root = root[: -len(prefix)]
    return root, prefix


def call(url: str, token: str = "", timeout: float = 15.0) -> tuple[int, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"cannot reach {url}: {exc.reason}") from exc


def pretty(body: str) -> str:
    body = body.strip()
    if not body:
        return "(empty response body)"
    try:
        return json.dumps(json.loads(body), ensure_ascii=False, indent=2)
    except ValueError:
        return body


def describe_error(body: str) -> str:
    try:
        payload = json.loads(body)
    except ValueError:
        return body.strip() or "(empty response body)"
    if isinstance(payload, dict):
        return str(payload.get("error") or payload.get("message") or payload)
    return str(payload)


def main() -> int:
    # Keep progress lines in order with anything written to stderr.
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description="Test connectivity and API token for a MyNexus server.")
    parser.add_argument(
        "--host",
        "--url",
        dest="host",
        default=os.environ.get("MYNEXUS_BASE_URL") or os.environ.get("MYNEXUS_API_URL"),
        help="MyNexus base URL, e.g. http://127.0.0.1:8080 (default: MYNEXUS_BASE_URL / MYNEXUS_API_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("MYNEXUS_API_TOKEN") or os.environ.get("MYNEXUS_TOKEN") or os.environ.get("MNX_TOKEN"),
        help="API token (default: MYNEXUS_API_TOKEN / MYNEXUS_TOKEN / MNX_TOKEN)",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="per-request timeout in seconds (default: 15)")
    args = parser.parse_args()

    if not args.host:
        parser.error("--host is required (or set MYNEXUS_BASE_URL)")
    if not args.token:
        parser.error("--token is required (or set MYNEXUS_API_TOKEN)")

    root, prefix = normalize_host(args.host)
    print(f"Host : {root}")
    print(f"Token: {args.token[:6]}{'*' * max(0, len(args.token) - 6)}")
    print()

    healthy = True

    # 1) Public health probe: proves the host is reachable and the service is up.
    health_url = root + "/healthz"
    print(f"[1/2] GET {health_url}")
    started = time.monotonic()
    try:
        status, body = call(health_url, timeout=args.timeout)
    except RuntimeError as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        return 1
    elapsed_ms = (time.monotonic() - started) * 1000
    print(f"  HTTP {status} ({elapsed_ms:.0f}ms)")
    print(pretty(body))
    print()
    if status != 200:
        healthy = False

    # 2) Authenticated probe: proves the token is valid. /system/health is
    # admin-only, so a bad or missing token surfaces as 401 instead of 404.
    auth_url = root + prefix + "/system/health"
    print(f"[2/2] GET {auth_url}")
    started = time.monotonic()
    try:
        status, body = call(auth_url, args.token, args.timeout)
    except RuntimeError as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        return 1
    elapsed_ms = (time.monotonic() - started) * 1000
    print(f"  HTTP {status} ({elapsed_ms:.0f}ms)")
    print(pretty(body))
    print()

    if status == 200:
        print("Connection OK: host is reachable and the API token is valid.")
        return 0 if healthy else 1
    if status in (401, 403):
        print(f"Authentication failed: {describe_error(body)}", file=sys.stderr)
        print("Check that --token is a valid, non-revoked API token.", file=sys.stderr)
    else:
        print(
            f"Unexpected response: {describe_error(body)}\n"
            f"Check that --host points at core-api (default port 8080) and that {prefix} is exposed.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
