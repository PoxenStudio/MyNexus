from abc import ABC, abstractmethod
from typing import Any


class BaseNode(ABC):
    """Base class every capability node (parser/cleaner/splitter/embedder/llm) implements."""

    @abstractmethod
    def process(self, input_data: Any) -> Any:
        ...

    @property
    @abstractmethod
    def node_name(self) -> str:
        ...
