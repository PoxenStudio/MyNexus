"""Per-call LLM request/response capture, gated by config.yaml's
debug.llm_logging ("打开调试日志" in the system settings page — see
config.WorkerConfig.debug_llm_logging and docs/部署说明.md).

Each call writes a matched pair of files under the OS temp dir:

    <tempdir>/mynexus-llm-debug/<timestamp>-<id>.request.json
    <tempdir>/mynexus-llm-debug/<timestamp>-<id>.response.txt

The request file has everything needed to replay the call (provider,
base_url, model, the exact messages sent); the response file is the
concatenated reply text, or the error if the call failed. Replay a captured
pair with:

    python3 worker/tests/replay_llm_debug.py /tmp/mynexus-llm-debug/<ts>-<id>.request.json
"""

import json
import tempfile
import time
import uuid
from pathlib import Path

_DIR_NAME = "mynexus-llm-debug"


def debug_dir() -> Path:
    d = Path(tempfile.gettempdir()) / _DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


class LLMCallLogger:
    """One instance per LLM call. Construct it right before the call (writes
    the request file immediately, so a hung/crashed call still leaves a
    record of what was sent), then call log_response() or log_error() once
    the call finishes."""

    def __init__(self, provider: str, model: str, base_url: str, messages: list[dict]) -> None:
        ts = time.strftime("%Y%m%d-%H%M%S")
        call_id = f"{ts}-{uuid.uuid4().hex[:8]}"
        self._dir = debug_dir()
        self.request_path = self._dir / f"{call_id}.request.json"
        self.response_path = self._dir / f"{call_id}.response.txt"
        self._started = time.monotonic()

        self.request_path.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "provider": provider,
                    "base_url": base_url,
                    "model": model,
                    "messages": messages,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)

    def log_response(self, text: str) -> None:
        self.response_path.write_text(f"# elapsed_ms={self._elapsed_ms()}\n{text}", encoding="utf-8")

    def log_error(self, exc: BaseException) -> None:
        self.response_path.write_text(
            f"# elapsed_ms={self._elapsed_ms()}\n# ERROR: {exc.__class__.__name__}: {exc}\n", encoding="utf-8"
        )
