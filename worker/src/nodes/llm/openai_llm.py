import json
import urllib.request
from typing import Iterator

from nodes.llm.base_llm import BaseLLM
from util.http import urlopen


class OpenAILLM(BaseLLM):
    """Calls any OpenAI-compatible /chat/completions endpoint (OpenAI, DeepSeek, etc.)
    with stream=true and yields text deltas as they arrive."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

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
        with urlopen(req, timeout=120) as resp:
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
                    yield content


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
