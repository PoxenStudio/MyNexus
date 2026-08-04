import json
import os
import threading

import numpy as np

from vector_store.base_store import BaseVectorStore

_LOCK = threading.Lock()


class SimpleVectorStore(BaseVectorStore):
    """Brute-force cosine-similarity store, persisted as one JSON file.

    Deliberately dependency-light (numpy only, no C-extension vector DB) to
    fit the NAS memory budget — see docs/系统设计文档.md §3.4. Fine for a
    personal library's chunk count (thousands, not millions); a real
    Chroma/Qdrant/pgvector backend can implement BaseVectorStore later
    without touching pipeline code if that stops being true.
    """

    def __init__(self, path: str) -> None:
        self.file_path = os.path.join(path, "chunks.json")
        os.makedirs(path, exist_ok=True)

    @property
    def node_name(self) -> str:
        return "simple_vector_store"

    def _load(self) -> list[dict]:
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, records: list[dict]) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)

    def upsert(self, chunks: list, vectors: list[list[float]]) -> None:
        with _LOCK:
            records = self._load()
            by_id = {r["id"]: r for r in records}
            for chunk, vector in zip(chunks, vectors):
                by_id[chunk.id] = {
                    "id": chunk.id,
                    "book_id": chunk.book_id,
                    "chapter_id": chunk.chapter_id,
                    "content": chunk.content,
                    "position": chunk.position,
                    "token_count": chunk.token_count,
                    "vector": vector,
                }
            self._save(list(by_id.values()))

    def delete_by_book(self, book_id: str) -> None:
        with _LOCK:
            records = [r for r in self._load() if r["book_id"] != book_id]
            self._save(records)

    def all(self, book_ids: list[str] | None = None) -> list[dict]:
        records = self._load()
        if book_ids:
            records = [r for r in records if r["book_id"] in book_ids]
        return records

    def search(self, query_vector: list[float], top_k: int, book_ids: list[str] | None = None) -> list[dict]:
        records = self.all(book_ids)
        if not records:
            return []

        query = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query) or 1.0

        scored = []
        for r in records:
            vec = np.array(r["vector"], dtype=np.float32)
            denom = (np.linalg.norm(vec) or 1.0) * query_norm
            score = float(np.dot(query, vec) / denom)
            scored.append((score, r))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [{**r, "score": score} for score, r in scored[:top_k]]


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m vector_store.simple_store /tmp/vstest
    import argparse

    from schemas.document import Chunk

    parser = argparse.ArgumentParser(description="Smoke-test the local vector store with fake vectors.")
    parser.add_argument("path")
    args = parser.parse_args()

    store = SimpleVectorStore(args.path)
    chunks = [
        Chunk(id="c1", book_id="b1", chapter_id="ch1", content="hello world", position=0, token_count=2),
        Chunk(id="c2", book_id="b1", chapter_id="ch1", content="goodbye world", position=1, token_count=2),
    ]
    store.upsert(chunks, [[1.0, 0.0], [0.0, 1.0]])
    results = store.search([0.9, 0.1], top_k=2)
    for r in results:
        print(f"score={r['score']:.3f} content={r['content']!r}")
