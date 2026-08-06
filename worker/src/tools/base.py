from abc import ABC, abstractmethod


class BaseTool(ABC):
    """A single LLM-callable "system status" tool for the chat assistant (see
    .claude/memory/mynexus_chat_tool_calling.md). Each tool declares an
    OpenAI-style function schema (name/description/parameters) and knows how
    to execute itself against Worker's own dependencies (CoreApiClient,
    retrieval, ...) — pipelines/qa.py never special-cases individual tools,
    it only ever talks to a ToolRegistry (see registry.py).

    Answers questions RAG retrieval structurally can't (e.g. "how many books
    are ingested" — that count doesn't live inside any book's content), as
    opposed to the existing citation flow which stays the answer path for
    everything else.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    def parameters(self) -> dict:
        """JSON Schema for the tool's arguments, OpenAI function-calling
        format. Defaults to "no arguments" — most system-status tools need
        none; override for ones that take a filter/lookup key."""
        return {"type": "object", "properties": {}}

    @abstractmethod
    def run(self, **kwargs) -> dict:
        """Executes the tool and returns a JSON-serializable result (fed back
        to the LLM as a tool-result message)."""
        ...

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }
