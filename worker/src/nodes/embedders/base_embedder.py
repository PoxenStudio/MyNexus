from abc import abstractmethod

from nodes.base import BaseNode


class BaseEmbedder(BaseNode):
    """Turns text into vectors. Concrete OpenAI/Ollama embedders land in M3."""

    @abstractmethod
    def process(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def embedding_dimension(self) -> int:
        ...
