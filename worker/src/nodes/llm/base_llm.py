from abc import abstractmethod
from typing import Iterator

from nodes.base import BaseNode


class BaseLLM(BaseNode):
    """Chat-completion node. Concrete OpenAI/Ollama-compatible clients land in M3."""

    @abstractmethod
    def process(self, messages: list[dict]) -> Iterator[str]:
        ...
