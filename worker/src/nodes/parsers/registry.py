from nodes.parsers.base_parser import BaseParser


class ParserRegistry:
    """Picks a parser by file suffix. Populated as parsers land in M2."""

    def __init__(self) -> None:
        self._parsers: dict[str, BaseParser] = {}

    def register(self, parser: BaseParser) -> None:
        for suffix in parser.supported_formats():
            self._parsers[suffix.lower()] = parser

    def get_parser(self, file_path: str) -> BaseParser:
        suffix = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        if suffix not in self._parsers:
            raise ValueError(f"no parser registered for suffix '{suffix}'")
        return self._parsers[suffix]
