import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Iterator

from nodes.llm.base_llm import BaseLLM, LLMUsage, _UsageIterator
from util.debug_log import LLMCallLogger
from util.http import ServiceCallError, call_provider, set_stream_idle_timeout

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_SECONDS = 30
_STREAM_IDLE_TIMEOUT_SECONDS = 90
_PROGRESS_LOG_CHUNK_INTERVAL = 20
_PROGRESS_LOG_TIME_INTERVAL_SECONDS = 30


def _parse_tool_calls(message: dict) -> list[dict]:
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            arguments = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        calls.append({"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": arguments})
    return calls


def _is_socket_timeout(exc: Exception) -> bool:
    if isinstance(exc, socket.timeout):
        return True
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, socket.timeout):
        return True
    return False


def _raise_service_timeout(exc: Exception) -> None:
    raise ServiceCallError(
        f"LLM 服务长时间无响应（{_STREAM_IDLE_TIMEOUT_SECONDS}s 内未收到任何有效内容），"
        f"可能是服务端故障或网络中断，请稍后重试"
    ) from exc


class _AppLevelIdleTimeout(Exception):
    """Raised when the stream has been open for _STREAM_IDLE_TIMEOUT_SECONDS without
    producing a single meaningful chunk (SSE keepalive/comment lines don't count)."""


class OpenAILLM(BaseLLM):
    """Calls any OpenAI-compatible /chat/completions endpoint (OpenAI, DeepSeek, etc.)
    with stream=true and yields text deltas as they arrive."""

    _MAX_OUTPUT_TOKENS = 8192

    def __init__(self, api_key: str, base_url: str, model: str, debug: bool = False) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.debug = debug

    @property
    def node_name(self) -> str:
        return "openai_llm"

    def process(self, messages: list[dict], call_site: str = "") -> _UsageIterator:
        usage = LLMUsage(provider="openai", model=self.model, call_site=call_site)
        body_len = sum(len(m.get("content", "") or "") for m in messages)

        def _gen() -> Iterator[str]:
            t_start = time.time()
            t_last_progress = t_start
            last_data_time = [t_start]
            payload = json.dumps(
                {
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    "max_tokens": self._MAX_OUTPUT_TOKENS,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=payload,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "text/event-stream",
                },
            )
            llm_log = LLMCallLogger("openai", self.model, self.base_url, messages) if self.debug else None
            chunks: list[str] = []
            total_chars = 0
            total_lines = 0
            stop_event = threading.Event()
            timer_error = [None]

            def _idle_watcher():
                while not stop_event.is_set():
                    elapsed = time.time() - last_data_time[0]
                    if elapsed > _STREAM_IDLE_TIMEOUT_SECONDS:
                        timer_error[0] = _AppLevelIdleTimeout(
                            f"no meaningful chunk for {elapsed:.0f}s"
                        )
                        return
                    stop_event.wait(5)

            watcher = threading.Thread(target=_idle_watcher, daemon=True)
            watcher.start()

            logger.info(
                "LLM stream start: call_site=%s model=%s base_url=%s body=%dchars connect_timeout=%ds app_idle_timeout=%ds",
                call_site, self.model, self.base_url, body_len, _CONNECT_TIMEOUT_SECONDS, _STREAM_IDLE_TIMEOUT_SECONDS,
            )
            try:
                t_connect_start = time.time()
                with call_provider(
                    req, timeout=_CONNECT_TIMEOUT_SECONDS,
                    service="llm", provider="openai", model=self.model,
                ) as resp:
                    t_connected = time.time()
                    set_stream_idle_timeout(resp, _STREAM_IDLE_TIMEOUT_SECONDS)
                    logger.info(
                        "LLM stream connected: call_site=%s connect_took=%.1fs",
                        call_site, t_connected - t_connect_start,
                    )
                    for raw_line in resp:
                        if timer_error[0] is not None:
                            raise timer_error[0]
                        total_lines += 1
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            last_data_time[0] = time.time()
                            logger.debug("openai stream bad json: %s", data[:100])
                            continue
                        last_data_time[0] = time.time()
                        if event.get("usage"):
                            u = event["usage"]
                            usage.prompt_tokens = int(u.get("prompt_tokens", 0))
                            usage.completion_tokens = int(u.get("completion_tokens", 0))
                            usage.total_tokens = int(u.get("total_tokens", 0))
                            continue
                        choices = event.get("choices")
                        if not choices:
                            logger.debug("openai stream chunk without choices: %s", data[:200])
                            continue
                        choice = choices[0]
                        finish = choice.get("finish_reason")
                        if finish:
                            usage.finish_reason = finish
                        delta = choice.get("delta", {})
                        content = delta.get("content")
                        if content:
                            total_chars += len(content)
                            if llm_log:
                                chunks.append(content)
                            yield content
                            if (
                                total_chars >= _PROGRESS_LOG_CHUNK_INTERVAL
                                or time.time() - t_last_progress >= _PROGRESS_LOG_TIME_INTERVAL_SECONDS
                            ):
                                logger.debug(
                                    "LLM streaming: call_site=%s elapsed=%.1fs lines=%d chars=%d",
                                    call_site, time.time() - t_start, total_lines, total_chars,
                                )
                                t_last_progress = time.time()
                                total_chars = 0
            except _AppLevelIdleTimeout:
                raise ServiceCallError(
                    f"LLM 服务长时间无响应（{_STREAM_IDLE_TIMEOUT_SECONDS}s 内未返回任何有效内容），"
                    f"可能是服务端故障或网络中断，请稍后重试"
                )
            except Exception as exc:
                t_elapsed = time.time() - t_start
                if _is_socket_timeout(exc):
                    logger.warning(
                        "LLM stream socket TIMEOUT: call_site=%s elapsed=%.1fs total_chars=%d lines=%d timeout=%ds",
                        call_site, t_elapsed, sum(len(c) for c in chunks), total_lines, _STREAM_IDLE_TIMEOUT_SECONDS,
                    )
                    _raise_service_timeout(exc)
                logger.error(
                    "LLM stream ERROR: call_site=%s elapsed=%.1fs total_chars=%d lines=%d error_type=%s error=%s",
                    call_site, t_elapsed, sum(len(c) for c in chunks), total_lines, type(exc).__name__, str(exc)[:200],
                )
                if llm_log:
                    llm_log.log_error(exc)
                raise
            else:
                t_elapsed = time.time() - t_start
                total_text = "".join(chunks)
                if llm_log:
                    llm_log.log_response(total_text)
                logger.info(
                    "LLM stream done: call_site=%s elapsed=%.1fs finish_reason=%s usage=(prompt=%d completion=%d total=%d) chars=%d lines=%d",
                    call_site, t_elapsed, usage.finish_reason or "-",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                    len(total_text), total_lines,
                )
            finally:
                stop_event.set()

        return _UsageIterator(_gen(), usage)

    def call(self, messages: list[dict], tools: list[dict] | None = None, call_site: str = "") -> dict:
        body: dict = {"model": self.model, "messages": messages, "stream": False, "max_tokens": self._MAX_OUTPUT_TOKENS}
        if tools:
            body["tools"] = tools
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
        )
        body_len = sum(len(m.get("content", "") or "") for m in messages)
        t_start = time.time()
        logger = LLMCallLogger("openai", self.model, self.base_url, messages) if self.debug else None
        logger.info(
            "LLM call start: call_site=%s model=%s base_url=%s body=%dchars",
            call_site, self.model, self.base_url, body_len,
        )
        try:
            with call_provider(
                req, timeout=_CONNECT_TIMEOUT_SECONDS,
                service="llm", provider="openai", model=self.model,
            ) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            t_elapsed = time.time() - t_start
            if _is_socket_timeout(exc):
                logger.warning("LLM call TIMEOUT: call_site=%s elapsed=%.1fs", call_site, t_elapsed)
                _raise_service_timeout(exc)
            logger.error(
                "LLM call ERROR: call_site=%s elapsed=%.1fs error_type=%s error=%s",
                call_site, t_elapsed, type(exc).__name__, str(exc)[:200],
            )
            if logger:
                logger.log_error(exc)
            raise
        message = data["choices"][0]["message"]
        result = {"content": message.get("content"), "tool_calls": _parse_tool_calls(message)}
        u = data.get("usage") or {}
        result["usage"] = LLMUsage(
            prompt_tokens=int(u.get("prompt_tokens", 0)),
            completion_tokens=int(u.get("completion_tokens", 0)),
            total_tokens=int(u.get("total_tokens", 0)),
            provider="openai",
            model=self.model,
            call_site=call_site,
            finish_reason=(data.get("choices") or [{}])[0].get("finish_reason", ""),
        )
        if logger:
            logged = {k: v for k, v in result.items() if k != "usage"}
            logger.log_response(json.dumps(logged, ensure_ascii=False))
        logger.info(
            "LLM call done: call_site=%s elapsed=%.1fs usage=(prompt=%d completion=%d total=%d) finish_reason=%s",
            call_site, time.time() - t_start,
            result["usage"].prompt_tokens, result["usage"].completion_tokens, result["usage"].total_tokens,
            result["usage"].finish_reason or "-",
        )
        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stream a chat completion from an OpenAI-compatible API.")
    parser.add_argument("prompt")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    llm = OpenAILLM(args.api_key, args.base_url, args.model)
    stream = llm.process([{"role": "user", "content": args.prompt}])
    for delta in stream:
        print(delta, end="", flush=True)
    print(f"\nusage={stream.usage}")
