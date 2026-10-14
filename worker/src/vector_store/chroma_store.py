import logging

import chromadb
from chromadb.errors import InvalidArgumentError

from vector_store.base_store import BaseVectorStore

logger = logging.getLogger(__name__)

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
        dim = len(vectors[0])
        stored = self._stored_dim()
        if stored and stored != dim:
            self._reset_collection(dim)
        try:
            self._upsert_batch(chunks, vectors)
        except InvalidArgumentError as e:
            if "dimension" not in str(e).lower():
                raise
            self._reset_collection(dim)
            self._upsert_batch(chunks, vectors)

    def _upsert_batch(self, chunks: list, vectors: list[list[float]]) -> None:
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
                    "start_offset": getattr(c, "start_offset", 0),
                    "end_offset": getattr(c, "end_offset", 0),
                }
                for c in chunks
            ],
        )

    def _stored_dim(self) -> int:
        try:
            return int((self.collection.metadata or {}).get("embedding_dim") or 0)
        except (TypeError, ValueError):
            return 0

    def _reset_collection(self, dim: int) -> None:
        logger.warning(
            "embedding dimension changed; dropping collection %r and all indexed vectors — rebuild every book",
            _COLLECTION_NAME,
        )
        self.client.delete_collection(_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            _COLLECTION_NAME, metadata={"hnsw:space": "cosine", "embedding_dim": str(dim)}
        )

    def delete_by_book(self, book_id: str) -> None:
        self.collection.delete(where={"book_id": book_id})

    def export_by_book(self, book_id: str, offset: int, limit: int) -> list[dict]:
        result = self.collection.get(
            where={"book_id": book_id},
            limit=limit,
            offset=offset,
            include=["documents", "metadatas", "embeddings"],
        )
        return [
            {
                **self._to_record(result["ids"][i], result["metadatas"][i], result["documents"][i]),
                "vector": result["embeddings"][i].tolist(),
            }
            for i in range(len(result["ids"]))
        ]

    def import_records(self, book_id: str, records: list[dict]) -> None:
        if not records:
            return
        self.collection.upsert(
            ids=[book_id + ":" + record["id"] for record in records],
            embeddings=[record["vector"] for record in records],
            documents=[record["content"] for record in records],
            metadatas=[
                {
                    "book_id": book_id,
                    "chapter_id": record["chapter_id"],
                    "position": record["position"],
                    "token_count": record["token_count"],
                    "start_offset": record["start_offset"],
                    "end_offset": record["end_offset"],
                }
                for record in records
            ],
        )

    def _ids_for_book(self, book_id: str) -> list[str]:
        return self.collection.get(where={"book_id": book_id}, include=[])["ids"]

    def _upsert_records(self, records: list[dict]) -> None:
        if not records:
            return
        self.collection.upsert(
            ids=[record["id"] for record in records],
            documents=[record["content"] for record in records],
            metadatas=[record["metadata"] for record in records],
            embeddings=[record["embedding"] for record in records],
        )

    def _records_by_ids(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        result = self.collection.get(
            ids=ids,
            include=["documents", "metadatas", "embeddings"],
        )
        records = []
        for i, old_id in enumerate(result["ids"]):
            records.append(
                {
                    "id": old_id,
                    "content": result["documents"][i],
                    "metadata": result["metadatas"][i],
                    "embedding": result["embeddings"][i].tolist(),
                }
            )
        return records

    def commit_import(self, book_id: str, staging_book_id: str, backup_book_id: str) -> None:
        old_ids = self._ids_for_book(book_id)
        stage_ids = self._ids_for_book(staging_book_id)
        try:
            for start in range(0, len(old_ids), 128):
                old_records = self._records_by_ids(old_ids[start : start + 128])
                for record in old_records:
                    original_id = record["id"]
                    record["id"] = backup_book_id + ":" + original_id
                    record["metadata"]["transfer_original_id"] = original_id
                    record["metadata"]["book_id"] = backup_book_id
                self._upsert_records(old_records)
            self.delete_by_book(book_id)
        except Exception:
            self.delete_by_book(backup_book_id)
            raise

        try:
            for start in range(0, len(stage_ids), 128):
                batch_ids = stage_ids[start : start + 128]
                result = self.collection.get(
                    ids=batch_ids,
                    include=["documents", "metadatas", "embeddings"],
                )
                records = []
                for i, old_id in enumerate(result["ids"]):
                    metadata = result["metadatas"][i]
                    metadata["book_id"] = book_id
                    records.append(
                        {
                            "id": old_id.removeprefix(staging_book_id + ":"),
                            "content": result["documents"][i],
                            "metadata": metadata,
                            "embedding": result["embeddings"][i].tolist(),
                        }
                    )
                self._upsert_records(records)
            self.delete_by_book(staging_book_id)
        except Exception:
            self.rollback_import(book_id, staging_book_id, backup_book_id)
            raise

    def rollback_import(self, book_id: str, staging_book_id: str, backup_book_id: str) -> None:
        self.delete_by_book(book_id)
        self.delete_by_book(staging_book_id)
        backup_ids = self._ids_for_book(backup_book_id)
        for start in range(0, len(backup_ids), 128):
            batch_ids = backup_ids[start : start + 128]
            result = self.collection.get(
                ids=batch_ids,
                include=["documents", "metadatas", "embeddings"],
            )
            records = []
            for i, backup_id in enumerate(result["ids"]):
                metadata = result["metadatas"][i]
                original_id = metadata.pop("transfer_original_id", backup_id.removeprefix(backup_book_id + ":"))
                metadata["book_id"] = book_id
                records.append(
                    {
                        "id": original_id,
                        "content": result["documents"][i],
                        "metadata": metadata,
                        "embedding": result["embeddings"][i].tolist(),
                    }
                )
            self._upsert_records(records)
        self.delete_by_book(backup_book_id)

    def finalize_import(self, staging_book_id: str, backup_book_id: str) -> None:
        self.delete_by_book(staging_book_id)
        self.delete_by_book(backup_book_id)

    def all(self, book_ids: list[str] | None = None) -> list[dict]:
        where = {"book_id": {"$in": book_ids}} if book_ids else None
        result = self.collection.get(where=where, include=["documents", "metadatas"])
        return [self._to_record(result["ids"][i], result["metadatas"][i], result["documents"][i]) for i in range(len(result["ids"]))]

    def search(self, query_vector: list[float], top_k: int, book_ids: list[str] | None = None) -> list[dict]:
        where = {"book_id": {"$in": book_ids}} if book_ids else None
        try:
            result = self.collection.query(
                query_embeddings=[query_vector], n_results=top_k, where=where,
                include=["documents", "metadatas", "distances"],
            )
        except InvalidArgumentError as e:
            if "dimension" not in str(e).lower():
                raise
            logger.warning("query vector dimension mismatch with collection; returning no results — rebuild every book")
            return []
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
            "start_offset": metadata.get("start_offset", 0),
            "end_offset": metadata.get("end_offset", 0),
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
