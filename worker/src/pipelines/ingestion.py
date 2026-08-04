from nodes.parsers.registry import ParserRegistry


class IngestionPipeline:
    """Orchestrates Parse -> Clean -> Split -> Embed. Steps are wired up in M2/M3;
    for now this only exposes readiness so /internal/pipeline can report status."""

    def __init__(self) -> None:
        self.parser_registry = ParserRegistry()

    def status(self) -> dict:
        return {
            "status": "ready",
            "pipeline": "ingestion",
            "stages": ["parse", "clean", "split", "embed"],
        }


def build_status() -> dict:
    return IngestionPipeline().status()
