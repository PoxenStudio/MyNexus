from abc import abstractmethod
from typing import Iterator

from nodes.base import BaseNode


class BaseLLM(BaseNode):
    """Chat-completion node. Concrete OpenAI/Ollama-compatible clients land in M3."""

    @abstractmethod
    def process(self, messages: list[dict]) -> Iterator[str]:
        ...

    @abstractmethod
    def call(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Single non-streaming request, optionally offering `tools` (OpenAI
        function-calling schema — see tools/base.py's BaseTool.to_schema).
        Used for the tool-call decision step (see pipelines/qa.py), which
        needs a single structured response rather than a token stream.

        Returns {"content": str | None, "tool_calls": [{"id", "name",
        "arguments": dict}, ...]} — tool_calls is an empty list when the
        model answered directly instead of calling a tool.
        """
        ...
