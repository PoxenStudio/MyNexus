#!/usr/bin/env python3
"""
Trigger and monitor a server-side export of one book's derived data.
Example:
  MYNEXUS_EXPORT_TOKEN=<token> python export_book_data.py --api-url http://127.0.0.1:3030/api/v1 <book id>
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url: str, token: str, *, body: dict | None = None) -> tuple[int, dict | None]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return 404, None
        message = exc.read().decode("utf-8", errors="replace").strip()
        if not message and exc.code in (502, 503, 504):
            message = "empty response body, usually a local HTTP proxy or an unreachable backend (use 127.0.0.1 instead of localhost)"
        raise RuntimeError(f"API returned HTTP {exc.code}: {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"cannot reach MyNexus API: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one book's summaries, keywords and vectors to ZIP.")
    parser.add_argument("book_id", help="MyNexus book id")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("MYNEXUS_API_URL", "http://127.0.0.1:3000/api/v1"),
        help="API base URL including the /api/v1 prefix (default: MYNEXUS_API_URL or http://127.0.0.1:3000/api/v1)",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "export",
        help="host path mapped to the server's /data directory or its export subdirectory (default: <repo>/data/export)",
    )
    parser.add_argument("--poll-interval", type=float, default=2.0, help="progress polling interval in seconds")
    parser.add_argument("--timeout", type=float, default=1800.0, help="maximum wait in seconds")
    args = parser.parse_args()

    token = os.environ.get("MYNEXUS_EXPORT_TOKEN", "")
    if not token:
        parser.error("MYNEXUS_EXPORT_TOKEN must contain the dedicated export API token")
    if args.poll_interval <= 0 or args.timeout <= 0:
        parser.error("--poll-interval and --timeout must be positive")

    base_url = args.api_url.rstrip("/")
    try:
        _, task = request_json(
            f"{base_url}/internal/book-data/exports",
            token,
            body={"book_id": args.book_id},
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not task or not task.get("id") or not task.get("target_file_name"):
        print("Export API returned an incomplete task response", file=sys.stderr)
        return 1

    task_id = task["id"]
    file_name = task["target_file_name"]
    if Path(file_name).name != file_name or not file_name.endswith(".zip"):
        print("Export API returned an unsafe target filename", file=sys.stderr)
        return 1
    output_path = args.export_dir / file_name
    deadline = time.monotonic() + args.timeout
    last_status = ""

    def find_output() -> Path | None:
        for candidate in (output_path, args.export_dir / "export" / file_name):
            if candidate.is_file():
                return candidate
        return None

    while time.monotonic() < deadline:
        try:
            status_code, current = request_json(
                f"{base_url}/internal/book-data/exports/{task_id}", token
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if status_code == 404:
            found = find_output()
            if found is not None:
                print(f"Export complete: {found}")
                return 0
            print("Task is not queryable and its output file is not present yet; checking again.", file=sys.stderr)
        elif current:
            state = current.get("status", "unknown")
            progress = current.get("progress", 0)
            stage = current.get("stage", "")
            if state != last_status or state in ("pending", "processing"):
                print(f"Export {state}: {progress}% {stage}".rstrip(), flush=True)
                last_status = state
            if state == "completed":
                found = find_output()
                if found is not None:
                    print(f"Export complete: {found}")
                    return 0
                print(
                    f"Task completed but output file is missing, looked for {output_path} and "
                    f"{args.export_dir / 'export' / file_name}",
                    file=sys.stderr,
                )
                return 1
            if state == "failed":
                print(current.get("error_msg") or "Export failed", file=sys.stderr)
                return 1

        time.sleep(args.poll_interval)

    print(f"Timed out waiting for export task {task_id}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
