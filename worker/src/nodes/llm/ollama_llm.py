import json
import urllib.request
from typing import Iterator

from nodes.llm.base_llm import BaseLLM
from util.http import call_provider


class OllamaLLM(BaseLLM):
    """Calls a local/LAN Ollama server's /api/chat endpoint with stream=true."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def node_name(self) -> str:
        return "ollama_llm"

    def process(self, messages: list[dict]) -> Iterator[str]:
        payload = json.dumps({"model": self.model, "messages": messages, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with call_provider(req, timeout=120, service="llm", provider="ollama", model=self.model) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                event = json.loads(line)
                content = event.get("message", {}).get("content")
                if content:
                    yield content
                if event.get("done"):
                    break


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.llm.ollama_llm "say hi"
    import argparse

    parser = argparse.ArgumentParser(description="Stream a chat completion from Ollama.")
    parser.add_argument("prompt")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="llama3")
    args = parser.parse_args()

    llm = OllamaLLM(args.base_url, args.model)
    for delta in llm.process([{"role": "user", "content": args.prompt}]):
        print(delta, end="", flush=True)
    print()
