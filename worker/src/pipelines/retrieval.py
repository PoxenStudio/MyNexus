import logging
import re

import jieba
from rank_bm25 import BM25Okapi

from config import WorkerConfig, load_config
from grpc_client import CoreApiClient
from nodes.factory import get_embedder, get_vector_store

# jieba lazily builds its dictionary trie (~1s for the bundled dict) on first
# use — initialize() forces that to happen at import time instead, so the
# cost lands on worker startup rather than stalling the first real search
# request. setLogLevel silences jieba's own "Building prefix dict..."/
# "Loading model cost ..." INFO-level logging on that first use.
jieba.setLogLevel(logging.WARNING)
jieba.initialize()

# Drops jieba's punctuation/whitespace tokens (kept only if they contain at
# least one word character — CJK ideographs count as \w under Python's
# default Unicode-aware re), which are pure noise for BM25 term matching.
_WORD_RE = re.compile(r"\w")


def _tokenize(text: str) -> list[str]:
    return [tok for tok in jieba.lcut(text.lower()) if _WORD_RE.search(tok)]


class RetrievalPipeline:
    """Hybrid search: vector cosine similarity + BM25/GIN keyword score, fused
    by weighted sum. Degrades gracefully to keyword-only if the embedder call
    fails (e.g. no API key configured) so search stays usable offline.

    Keyword scoring has two implementations depending on the configured
    storage backend (see .claude/memory/mynexus_keyword_search_gin.md):
    - postgres: calls Core API's GIN-indexed KeywordSearch RPC (Core API owns
      the query; Worker never touches Postgres directly) — see grpc_client.py.
    - sqlite (small-scale/trial deployments only): the original in-process
      BM25-over-full-corpus pass, unchanged.
    """

    VECTOR_WEIGHT = 0.6
    KEYWORD_WEIGHT = 0.4

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.embedder = get_embedder(self.config)
        self.vector_store = get_vector_store(self.config)
        self.core_api = CoreApiClient(self.config)

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
        keyword_scores = self._keyword_scores(query, records, book_ids, top_k)

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

    def _keyword_scores(
        self, query: str, records: list[dict], book_ids: list[str] | None, top_k: int
    ) -> dict[str, float]:
        if self.config.storage_database == "postgres":
            scores = self._keyword_scores_gin(query, book_ids, top_k)
            if scores is not None:
                return scores
            # Core API unreachable / not yet migrated / returned an error —
            # fall back to the brute-force pass rather than losing the
            # keyword signal entirely for this query.
        return self._keyword_scores_bm25(query, records)

    def _keyword_scores_gin(self, query: str, book_ids: list[str] | None, top_k: int) -> dict[str, float] | None:
        results = self.core_api.keyword_search(query, book_ids, max(top_k * 4, 50))
        if results is None:
            return None
        if not results:
            return {}
        max_score = max(r["score"] for r in results)
        if max_score <= 0:
            return {}
        return {r["chunk_id"]: r["score"] / max_score for r in results}

    @staticmethod
    def _keyword_scores_bm25(query: str, records: list[dict]) -> dict[str, float]:
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
