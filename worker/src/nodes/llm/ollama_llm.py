import json
import logging
import urllib.request
from typing import Iterator

from nodes.llm.base_llm import BaseLLM, LLMUsage, _UsageIterator
from util.debug_log import LLMCallLogger
from util.http import call_provider, host_lock

logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """Calls a local/LAN Ollama server's /api/chat endpoint with stream=true."""

    _MAX_OUTPUT_TOKENS = 8192

    def __init__(self, base_url: str, model: str, debug: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.debug = debug

    @property
    def node_name(self) -> str:
        return "ollama_llm"

    def process(self, messages: list[dict], call_site: str = "") -> _UsageIterator:
        usage = LLMUsage(provider="ollama", model=self.model, call_site=call_site)

        def _gen() -> Iterator[str]:
            payload = json.dumps(
                {
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"num_predict": self._MAX_OUTPUT_TOKENS},
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            llm_log = LLMCallLogger("ollama", self.model, self.base_url, messages) if self.debug else None
            chunks: list[str] = []
            logger.debug("ollama stream start: call_site=%s model=%s num_predict=%d", call_site, self.model, self._MAX_OUTPUT_TOKENS)
            try:
                with host_lock(self.base_url), call_provider(
                    req, timeout=120, service="llm", provider="ollama", model=self.model
                ) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        content = event.get("message", {}).get("content")
                        if content:
                            if llm_log:
                                chunks.append(content)
                            yield content
                        if event.get("done"):
                            usage.prompt_tokens = int(event.get("prompt_eval_count") or 0)
                            usage.completion_tokens = int(event.get("eval_count") or 0)
                            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                            usage.finish_reason = event.get("done_reason", "")
                            break
            except Exception as exc:
                logger.exception("ollama stream error: call_site=%s chunks_collected=%d", call_site, sum(len(c) for c in chunks))
                if llm_log:
                    llm_log.log_error(exc)
                raise
            else:
                if llm_log:
                    llm_log.log_response("".join(chunks))
                logger.debug(
                    "ollama stream done: call_site=%s finish_reason=%s usage=(prompt=%d completion=%d total=%d) chunks=%d",
                    call_site, usage.finish_reason or "-",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, len(chunks),
                )

        return _UsageIterator(_gen(), usage)

    def call(self, messages: list[dict], tools: list[dict] | None = None, call_site: str = "") -> dict:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": self._MAX_OUTPUT_TOKENS},
        }
        if tools:
            body["tools"] = tools
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        logger = LLMCallLogger("ollama", self.model, self.base_url, messages) if self.debug else None
        try:
            with host_lock(self.base_url), call_provider(
                req, timeout=120, service="llm", provider="ollama", model=self.model
            ) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            if logger:
                logger.log_error(exc)
            raise
        message = data.get("message", {})
        tool_calls = [
            {"id": "", "name": tc.get("function", {}).get("name", ""), "arguments": tc.get("function", {}).get("arguments", {})}
            for tc in message.get("tool_calls") or []
        ]
        result = {"content": message.get("content"), "tool_calls": tool_calls}
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        result["usage"] = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            provider="ollama",
            model=self.model,
            call_site=call_site,
            finish_reason=data.get("done_reason", ""),
        )
        if logger:
            logged = {k: v for k, v in result.items() if k != "usage"}
            logger.log_response(json.dumps(logged, ensure_ascii=False))
        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stream a chat completion from Ollama.")
    parser.add_argument("prompt")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="llama3")
    args = parser.parse_args()

    llm = OllamaLLM(args.base_url, args.model)
    stream = llm.process([{"role": "user", "content": args.prompt}])
    for delta in stream:
        print(delta, end="", flush=True)
    print(f"\nusage={stream.usage}")
