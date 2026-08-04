import chromadb

from vector_store.base_store import BaseVectorStore

_COLLECTION_NAME = "chunks"


class ChromaStore(BaseVectorStore):
    """ChromaDB-backed vector store (HNSW index, on-disk SQLite + binary index).

    Default backend as of M3 — see docs/系统设计文档.md §3.4: a brute-force
    numpy store re-parses its entire JSON file on every query, which is fine
    for a few thousand chunks but falls over long before "tens of thousands
    of books" scale. Chroma persists to disk and indexes properly instead of
    loading the whole corpus into memory per request.
    """

    def __init__(self, path: str) -> None:
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            _COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    @property
    def node_name(self) -> str:
        return "chroma_vector_store"

    def upsert(self, chunks: list, vectors: list[list[float]]) -> None:
        if not chunks:
            return
        self.collection.upsert(
            ids=[c.id for c in chunks],
            embeddings=vectors,
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    "book_id": c.book_id,
                    "chapter_id": c.chapter_id,
                    "position": c.position,
                    "token_count": c.token_count,
                }
                for c in chunks
            ],
        )

    def delete_by_book(self, book_id: str) -> None:
        self.collection.delete(where={"book_id": book_id})

    def all(self, book_ids: list[str] | None = None) -> list[dict]:
        where = {"book_id": {"$in": book_ids}} if book_ids else None
        result = self.collection.get(where=where, include=["documents", "metadatas"])
        return [self._to_record(result["ids"][i], result["metadatas"][i], result["documents"][i]) for i in range(len(result["ids"]))]

    def search(self, query_vector: list[float], top_k: int, book_ids: list[str] | None = None) -> list[dict]:
        where = {"book_id": {"$in": book_ids}} if book_ids else None
        result = self.collection.query(
            query_embeddings=[query_vector], n_results=top_k, where=where,
            include=["documents", "metadatas", "distances"],
        )
        if not result["ids"] or not result["ids"][0]:
            return []

        records = []
        for i in range(len(result["ids"][0])):
            record = self._to_record(result["ids"][0][i], result["metadatas"][0][i], result["documents"][0][i])
            # collection uses cosine *distance* (1 - cosine similarity); flip
            # back to a similarity score so callers see the same 0..1-ish
            # scale as SimpleVectorStore's raw cosine similarity.
            record["score"] = 1.0 - result["distances"][0][i]
            records.append(record)
        return records

    @staticmethod
    def _to_record(chunk_id: str, metadata: dict, content: str) -> dict:
        return {
            "id": chunk_id,
            "book_id": metadata.get("book_id", ""),
            "chapter_id": metadata.get("chapter_id", ""),
            "content": content,
            "position": metadata.get("position", 0),
            "token_count": metadata.get("token_count", 0),
        }


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m vector_store.chroma_store /tmp/chromatest
    import argparse

    from schemas.document import Chunk

    parser = argparse.ArgumentParser(description="Smoke-test the Chroma vector store with fake vectors.")
    parser.add_argument("path")
    args = parser.parse_args()

    store = ChromaStore(args.path)
    chunks = [
        Chunk(id="c1", book_id="b1", chapter_id="ch1", content="hello world", position=0, token_count=2),
        Chunk(id="c2", book_id="b1", chapter_id="ch1", content="goodbye world", position=1, token_count=2),
    ]
    store.upsert(chunks, [[1.0, 0.0], [0.0, 1.0]])
    results = store.search([0.9, 0.1], top_k=2)
    for r in results:
        print(f"score={r['score']:.3f} content={r['content']!r}")
