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

logger = logging.getLogger(__name__)
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

    RRF_K = 60

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.embedder = get_embedder(self.config)
        self.vector_store = get_vector_store(self.config)
        self.core_api = CoreApiClient(self.config)
        self.fusion = self.config.retrieval_fusion
        self.vector_weight = self.config.retrieval_vector_weight
        self.keyword_weight = self.config.retrieval_keyword_weight

    def search(
        self,
        query: str,
        book_ids: list[str] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        mode: str = "hybrid",
        fusion: str | None = None,
        include_summaries: bool = False,
    ) -> list[dict]:
        records = self.vector_store.all(book_ids)
        if not records:
            return []

        # Summary vectors ("{id}:summary") share the collection with real
        # chunks and outrank them on overview-ish queries; QA excludes them.
        vector_limit = len(records)
        if not include_summaries:
            records = [r for r in records if not r["id"].endswith(":summary")]

        return self._fuse(query, records, book_ids, top_k, score_threshold, mode, fusion, vector_limit)

    def search_by_chapter_route(
        self,
        query: str,
        book_ids: list[str] | None = None,
        chapter_top_n: int = 8,
        top_k: int = 10,
        mode: str = "hybrid",
    ) -> tuple[list[dict], list[dict]]:
        """Two-stage retrieval for cross-chapter questions (timelines, plot
        threads, character arcs): first aggregate chunk scores per chapter to
        pick candidate chapters, then re-rank only chunks within them.

        Routing uses chunk-level scores aggregated per chapter (top-3 sum) —
        chapter *summaries* proved useless as the routing corpus: LLM-written
        summaries generalize away proper nouns ("小沛" never appears in them),
        so BM25 scores zero and vector similarity alone routes every war-ish
        chapter to the top. Proper-noun hits cluster in the right chapters by
        construction, and top-3 summing suppresses chapters with a single
        lucky chunk.

        Returns (chunks, routed_chapters) where routed_chapters carries
        chapter_id, aggregate score, and the chapter summary text (when one
        exists) for display. Empty lists mean: fall back to plain search().
        """
        records = self.vector_store.all(book_ids)
        chunk_records = [r for r in records if not r["id"].endswith(":summary")]
        if not chunk_records:
            return [], []

        all_hits = self._fuse(
            query, chunk_records, book_ids, top_k=len(chunk_records), mode=mode, vector_limit=len(records)
        )
        by_chapter: dict[str, list[float]] = {}
        for hit in all_hits:
            if hit["score"] <= 0:
                continue
            by_chapter.setdefault(hit["chapter_id"], []).append(hit["score"])
        ranked = sorted(
            ((sum(scores[:3]), cid) for cid, scores in by_chapter.items()), reverse=True
        )[:chapter_top_n]
        if not ranked:
            return [], []

        summary_by_chapter = {
            r["chapter_id"]: r["content"]
            for r in records
            if r["id"].endswith(":summary") and r["chapter_id"]
        }
        book_by_chapter = {r["chapter_id"]: r["book_id"] for r in chunk_records}
        routed = [
            {"chapter_id": cid, "book_id": book_by_chapter[cid],
             "score": score, "summary": summary_by_chapter.get(cid, "")}
            for score, cid in ranked
        ]
        chapter_ids = {cid for _, cid in ranked}
        chunks = [r for r in chunk_records if r["chapter_id"] in chapter_ids]
        return self._fuse(query, chunks, book_ids, top_k, mode=mode, vector_limit=len(records)), routed

    def _fuse(
        self,
        query: str,
        records: list[dict],
        book_ids: list[str] | None,
        top_k: int,
        score_threshold: float = 0.0,
        mode: str = "hybrid",
        fusion: str | None = None,
        vector_limit: int | None = None,
    ) -> list[dict]:
        """Scores and ranks one record subset (chunks, or chapter summaries
        for routing) with the same vector+keyword fusion as search().
        vector_limit is the corpus size the vector pass scores — must cover
        the whole collection, not just the subset, or subset members get no
        vector score when they rank outside the store-wide top-n."""
        if not records:
            return []

        vector_scores: dict[str, float] = {}
        keyword_scores: dict[str, float] = {}
        if mode in ("hybrid", "vector"):
            vector_scores = self._vector_scores(query, book_ids, vector_limit or len(records))
        if mode in ("hybrid", "bm25"):
            keyword_scores = self._keyword_scores(query, records, book_ids, top_k)

        active_weights = {
            "vector": self.vector_weight if vector_scores else 0.0,
            "keyword": self.keyword_weight if keyword_scores else 0.0,
        }
        weight_sum = sum(active_weights.values())
        if weight_sum == 0:
            return []

        if (fusion or self.fusion) == "rrf":
            fused_scores = self._fuse_rrf(vector_scores, keyword_scores, active_weights)
        else:
            fused_scores = {
                r["id"]: (active_weights["vector"] * vector_scores.get(r["id"], 0.0)
                          + active_weights["keyword"] * keyword_scores.get(r["id"], 0.0)) / weight_sum
                for r in records
            }

        fused = []
        for r in records:
            v = vector_scores.get(r["id"], 0.0)
            k = keyword_scores.get(r["id"], 0.0)
            score = fused_scores.get(r["id"], 0.0)
            if score >= score_threshold:
                fused.append({**r, "score": score, "vector_score": v, "keyword_score": k})

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:top_k]

    def _fuse_rrf(
        self,
        vector_scores: dict[str, float],
        keyword_scores: dict[str, float],
        weights: dict[str, float],
    ) -> dict[str, float]:
        def ranks(scores: dict[str, float]) -> list[str]:
            return [cid for cid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]

        fused: dict[str, float] = {}
        for key, scores in (("vector", vector_scores), ("keyword", keyword_scores)):
            if not scores:
                continue
            w = weights[key] / (weights["vector"] + weights["keyword"])
            for rank, cid in enumerate(ranks(scores), start=1):
                fused[cid] = fused.get(cid, 0.0) + w / (self.RRF_K + rank)
        return fused

    def _vector_scores(self, query: str, book_ids: list[str] | None, limit: int) -> dict[str, float]:
        try:
            query_vector = self.embedder.process([query])[0]
        except Exception as exc:  # noqa: BLE001 - embedding provider may be unreachable/unconfigured
            logger.warning("embedder call failed, degrading to keyword-only retrieval: %s", exc)
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
