from nodes.embedders.base_embedder import BaseEmbedder


class LocalEmbedder(BaseEmbedder):
    """Runs an ONNX embedding model in-process via fastembed (no external service)."""

    def __init__(self, model: str, model_path: str = "") -> None:
        self.model = model
        self.model_path = model_path
        self._engine = None
        self._dimension = 0

    @property
    def node_name(self) -> str:
        return "local_embedder"

    def _load(self):
        if self._engine is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as e:
                raise RuntimeError("fastembed is required for embedding.provider=local") from e
            kwargs = {"cache_dir": self.model_path} if self.model_path else {}
            self._engine = TextEmbedding(self.model, **kwargs)
        return self._engine

    def process(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = [[float(x) for x in v] for v in self._load().embed(texts)]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def embedding_dimension(self) -> int:
        return self._dimension


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.embedders.local_embedder "hello world"
    import argparse

    parser = argparse.ArgumentParser(description="Embed one line of text with a local fastembed model.")
    parser.add_argument("text")
    parser.add_argument("--model", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    args = parser.parse_args()

    embedder = LocalEmbedder(args.model)
    vectors = embedder.process([args.text])
    print(f"dimension={embedder.embedding_dimension()} vector[:5]={vectors[0][:5]}")
