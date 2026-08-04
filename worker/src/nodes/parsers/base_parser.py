from abc import abstractmethod

from nodes.base import BaseNode
from schemas.document import ParsedDocument


class BaseParser(BaseNode):
    """Document parser interface. Concrete EPUB/TXT parsers land in M2.

    display_name is the original upload filename (not the on-disk path, which
    is keyed by book id) — formats with no embedded title metadata (TXT) fall
    back to it instead of showing a UUID.
    """

    @abstractmethod
    def process(self, file_path: str, display_name: str = "") -> ParsedDocument:
        ...

    @staticmethod
    @abstractmethod
    def supported_formats() -> list[str]:
        ...
