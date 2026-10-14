from abc import abstractmethod
from dataclasses import dataclass
from typing import Iterator

from nodes.base import BaseNode


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    provider: str = ""
    model: str = ""
    call_site: str = ""
    finish_reason: str = ""


class _UsageIterator(Iterator[str]):
    """Wraps an LLM stream generator; callers keep the same `for delta in
    llm.process(...)` loop, and once it finishes they read `.usage` for the
    token counts the provider reported (or 0 if the provider gave none)."""

    def __init__(self, gen: Iterator[str], usage: LLMUsage) -> None:
        self._gen = gen
        self.usage = usage

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        return next(self._gen)


class BaseLLM(BaseNode):
    """Chat-completion node. Concrete OpenAI/Ollama-compatible clients land in M3."""

    @abstractmethod
    def process(self, messages: list[dict], call_site: str = "") -> _UsageIterator:
        ...

    @abstractmethod
    def call(self, messages: list[dict], tools: list[dict] | None = None, call_site: str = "") -> dict:
        """Single non-streaming request, optionally offering `tools` (OpenAI
        function-calling schema — see tools/base.py's BaseTool.to_schema).
        Used for the tool-call decision step (see pipelines/qa.py), which
        needs a single structured response rather than a token stream.

        Returns {"content": str | None, "tool_calls": [{"id", "name",
        "arguments": dict}, ...], "usage": LLMUsage} — tool_calls is an empty
        list when the model answered directly instead of calling a tool."""
        ...
