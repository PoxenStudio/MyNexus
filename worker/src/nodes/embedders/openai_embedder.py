import json
import urllib.request

from nodes.embedders.base_embedder import BaseEmbedder
from util.http import urlopen

# OpenAI's text-embedding-3-small dimension; overridden by the first real
# response if the configured model differs (see embedding_dimension()).
_DEFAULT_DIMENSION = 1536


class OpenAIEmbedder(BaseEmbedder):
    """Calls any OpenAI-compatible /embeddings endpoint (OpenAI, DeepSeek, etc.)."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimension = _DEFAULT_DIMENSION

    @property
    def node_name(self) -> str:
        return "openai_embedder"

    def process(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())

        vectors = [item["embedding"] for item in sorted(body["data"], key=lambda d: d["index"])]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def embedding_dimension(self) -> int:
        return self._dimension


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.embedders.openai_embedder "hello world" --api-key sk-xxx --base-url http://localhost:9000/v1
    import argparse

    parser = argparse.ArgumentParser(description="Embed one line of text via an OpenAI-compatible API.")
    parser.add_argument("text")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--model", default="text-embedding-3-small")
    args = parser.parse_args()

    embedder = OpenAIEmbedder(args.api_key, args.base_url, args.model)
    vectors = embedder.process([args.text])
    print(f"dimension={embedder.embedding_dimension()} vector[:5]={vectors[0][:5]}")
