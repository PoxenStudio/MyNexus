import re

from rank_bm25 import BM25Okapi

from config import WorkerConfig, load_config
from nodes.factory import get_embedder, get_vector_store

# Crude CJK-aware tokenizer: ASCII words stay whole, each CJK character
# becomes its own token. Avoids pulling in a full segmenter (e.g. jieba) to
# keep the worker image small — see docs/系统设计文档.md §3.4.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class RetrievalPipeline:
    """Hybrid search: vector cosine similarity + BM25 keyword score, fused by
    weighted sum. Degrades gracefully to keyword-only if the embedder call
    fails (e.g. no API key configured) so search stays usable offline."""

    VECTOR_WEIGHT = 0.6
    KEYWORD_WEIGHT = 0.4

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.embedder = get_embedder(self.config)
        self.vector_store = get_vector_store(self.config)

    def search(
        self,
        query: str,
        book_ids: list[str] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        records = self.vector_store.all(book_ids)
        if not records:
            return []

        vector_scores = self._vector_scores(query, book_ids, len(records))
        keyword_scores = self._keyword_scores(query, records)

        fused = []
        for r in records:
            v = vector_scores.get(r["id"], 0.0)
            k = keyword_scores.get(r["id"], 0.0)
            weight_sum = (self.VECTOR_WEIGHT if vector_scores else 0) + self.KEYWORD_WEIGHT
            score = (self.VECTOR_WEIGHT * v + self.KEYWORD_WEIGHT * k) / weight_sum
            if score >= score_threshold:
                fused.append({**r, "score": score, "vector_score": v, "keyword_score": k})

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:top_k]

    def _vector_scores(self, query: str, book_ids: list[str] | None, limit: int) -> dict[str, float]:
        try:
            query_vector = self.embedder.process([query])[0]
        except Exception:  # noqa: BLE001 - embedding provider may be unreachable/unconfigured
            return {}
        results = self.vector_store.search(query_vector, top_k=limit, book_ids=book_ids)
        return {r["id"]: r["score"] for r in results}

    @staticmethod
    def _keyword_scores(query: str, records: list[dict]) -> dict[str, float]:
        tokenized_corpus = [_tokenize(r["content"]) for r in records]
        bm25 = BM25Okapi(tokenized_corpus)
        raw_scores = bm25.get_scores(_tokenize(query))
        max_score = max(raw_scores) if len(raw_scores) else 0.0
        if max_score <= 0:
            return {}
        return {records[i]["id"]: raw_scores[i] / max_score for i in range(len(records))}


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m pipelines.retrieval "search query" --path /tmp/vstest
    import argparse

    parser = argparse.ArgumentParser(description="Run hybrid search against the local vector store.")
    parser.add_argument("query")
    parser.add_argument("--path", default="./data/vectorstore")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    cfg = load_config()
    cfg.vector_store_path = args.path
    for r in RetrievalPipeline(cfg).search(args.query, top_k=args.top_k):
        print(f"score={r['score']:.3f} (v={r['vector_score']:.3f} k={r['keyword_score']:.3f}) {r['content'][:60]!r}")
