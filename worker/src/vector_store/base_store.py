from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    """Vector database driver interface. Concrete Chroma/pgvector drivers land in M3."""

    @abstractmethod
    def upsert(self, chunks: list, vectors: list[list[float]]) -> None:
        ...

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int) -> list:
        ...
