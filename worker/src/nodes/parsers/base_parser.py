from abc import abstractmethod

from nodes.base import BaseNode
from schemas.document import ParsedDocument


class BaseParser(BaseNode):
    """Document parser interface. Concrete EPUB/TXT parsers land in M2."""

    @abstractmethod
    def process(self, file_path: str) -> ParsedDocument:
        ...

    @staticmethod
    @abstractmethod
    def supported_formats() -> list[str]:
        ...
