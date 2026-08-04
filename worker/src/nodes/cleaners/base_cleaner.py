from abc import abstractmethod

from nodes.base import BaseNode


class BaseCleaner(BaseNode):
    """Text cleaning node interface."""

    @abstractmethod
    def process(self, text: str) -> str:
        ...
