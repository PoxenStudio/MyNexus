from abc import abstractmethod

from nodes.base import BaseNode
from schemas.document import Chunk, ParsedChapter


class BaseSplitter(BaseNode):
    """Splits a book's chapters into embeddable chunks."""

    @abstractmethod
    def process(self, book_id: str, chapters: list[ParsedChapter]) -> list[Chunk]:
        ...
