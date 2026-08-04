import json
import urllib.request

from nodes.embedders.base_embedder import BaseEmbedder
from util.http import urlopen


class OllamaEmbedder(BaseEmbedder):
    """Calls a local/LAN Ollama server's /api/embeddings endpoint."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimension = 0

    @property
    def node_name(self) -> str:
        return "ollama_embedder"

    def process(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/embeddings",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read())
            vectors.append(body["embedding"])
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def embedding_dimension(self) -> int:
        return self._dimension


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.embedders.ollama_embedder "hello world"
    import argparse

    parser = argparse.ArgumentParser(description="Embed one line of text via Ollama.")
    parser.add_argument("text")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="nomic-embed-text")
    args = parser.parse_args()

    embedder = OllamaEmbedder(args.base_url, args.model)
    vectors = embedder.process([args.text])
    print(f"dimension={embedder.embedding_dimension()} vector[:5]={vectors[0][:5]}")
