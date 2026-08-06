import json
import urllib.request
from typing import Iterator

from nodes.llm.base_llm import BaseLLM
from util.debug_log import LLMCallLogger
from util.http import call_provider


def _parse_tool_calls(message: dict) -> list[dict]:
    """Normalizes OpenAI's `message.tool_calls` shape (arguments is a JSON
    *string* on the wire) into the {"id", "name", "arguments": dict} shape
    BaseLLM.call documents — so pipelines/qa.py never has to know which
    provider answered."""
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            arguments = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        calls.append({"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": arguments})
    return calls


class OpenAILLM(BaseLLM):
    """Calls any OpenAI-compatible /chat/completions endpoint (OpenAI, DeepSeek, etc.)
    with stream=true and yields text deltas as they arrive."""

    def __init__(self, api_key: str, base_url: str, model: str, debug: bool = False) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        # See util/debug_log.py — dumps this call's request/response to the
        # OS temp dir when the system settings "打开调试日志" toggle is on.
        self.debug = debug

    @property
    def node_name(self) -> str:
        return "openai_llm"

    def process(self, messages: list[dict]) -> Iterator[str]:
        payload = json.dumps({"model": self.model, "messages": messages, "stream": True}).encode("utf-8")
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
        logger = LLMCallLogger("openai", self.model, self.base_url, messages) if self.debug else None
        chunks: list[str] = []
        try:
            with call_provider(req, timeout=120, service="llm", provider="openai", model=self.model) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    delta = event["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        if logger:
                            chunks.append(content)
                        yield content
        except Exception as exc:
            if logger:
                logger.log_error(exc)
            raise
        else:
            if logger:
                logger.log_response("".join(chunks))

    def call(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        body: dict = {"model": self.model, "messages": messages, "stream": False}
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
        except Exception as exc:
            if logger:
                logger.log_error(exc)
            raise
        message = data["choices"][0]["message"]
        result = {"content": message.get("content"), "tool_calls": _parse_tool_calls(message)}
        if logger:
            logger.log_response(json.dumps(result, ensure_ascii=False))
        return result


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.llm.openai_llm "say hi" --api-key sk-xxx --base-url http://localhost:9000/v1
    import argparse

    parser = argparse.ArgumentParser(description="Stream a chat completion from an OpenAI-compatible API.")
    parser.add_argument("prompt")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    llm = OpenAILLM(args.api_key, args.base_url, args.model)
    for delta in llm.process([{"role": "user", "content": args.prompt}]):
        print(delta, end="", flush=True)
    print()
