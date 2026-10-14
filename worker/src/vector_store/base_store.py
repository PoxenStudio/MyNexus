from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    """Vector database driver interface. Concrete Chroma/pgvector drivers land in M3."""

    @abstractmethod
    def upsert(self, chunks: list, vectors: list[list[float]]) -> None:
        ...

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int) -> list:
        ...

    def export_by_book(self, book_id: str, offset: int, limit: int) -> list[dict]:
        raise NotImplementedError(f"{type(self).__name__} does not support vector export")

    def import_records(self, book_id: str, records: list[dict]) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not support vector import")

    def commit_import(self, book_id: str, staging_book_id: str, backup_book_id: str) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not support vector import")

    def rollback_import(self, book_id: str, staging_book_id: str, backup_book_id: str) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not support vector import")

    def finalize_import(self, staging_book_id: str, backup_book_id: str) -> None:
        self.delete_by_book(staging_book_id)
        self.delete_by_book(backup_book_id)
