import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Iterator

from nodes.llm.base_llm import BaseLLM, LLMUsage, _UsageIterator
from util.debug_log import LLMCallLogger
from util.http import ServiceCallError, call_provider, set_stream_idle_timeout

logger = logging.getLogger(__name__)

_STREAM_IDLE_TIMEOUT_SECONDS = 90


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
        f"LLM 服务长时间无响应（{_STREAM_IDLE_TIMEOUT_SECONDS}s 内未收到任何数据），"
        f"可能是服务端故障或网络中断，请稍后重试"
    ) from exc


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

        def _gen() -> Iterator[str]:
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
            logger.debug("openai stream start: call_site=%s model=%s max_tokens=%d", call_site, self.model, self._MAX_OUTPUT_TOKENS)
            try:
                with call_provider(req, timeout=120, service="llm", provider="openai", model=self.model) as resp:
                    set_stream_idle_timeout(resp, _STREAM_IDLE_TIMEOUT_SECONDS)
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        event = json.loads(data)
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
                            if llm_log:
                                chunks.append(content)
                            yield content
            except Exception as exc:
                if _is_socket_timeout(exc):
                    logger.warning(
                        "openai stream idle timeout: call_site=%s chunks_collected=%d idle=%ds",
                        call_site, sum(len(c) for c in chunks), _STREAM_IDLE_TIMEOUT_SECONDS,
                    )
                    _raise_service_timeout(exc)
                logger.exception("openai stream error: call_site=%s chunks_collected=%d", call_site, sum(len(c) for c in chunks))
                if llm_log:
                    llm_log.log_error(exc)
                raise
            else:
                if llm_log:
                    llm_log.log_response("".join(chunks))
                logger.debug(
                    "openai stream done: call_site=%s finish_reason=%s usage=(prompt=%d completion=%d total=%d) chunks=%d",
                    call_site, usage.finish_reason or "-",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, len(chunks),
                )

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
        logger = LLMCallLogger("openai", self.model, self.base_url, messages) if self.debug else None
        try:
            with call_provider(req, timeout=120, service="llm", provider="openai", model=self.model) as resp:
                data = json.loads(resp.read())
            message = data["choices"][0]["message"]
        except Exception as exc:
            if _is_socket_timeout(exc):
                logger.warning("openai call timeout: call_site=%s", call_site)
                _raise_service_timeout(exc)
            if logger:
                logger.log_error(exc)
            raise
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
