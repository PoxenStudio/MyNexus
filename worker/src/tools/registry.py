from tools.base import BaseTool


class ToolRegistry:
    """Holds the tools offered to the LLM for one chat turn. QAPipeline builds
    one (see qa.py), passes `schemas()` to the tool-call decision step, and
    dispatches by name via `run()` when the model asks to call one — this is
    the only place that needs to know a registry exists; adding a new tool
    never touches qa.py's control flow, only the list passed to
    ToolRegistry(...)."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._tools = {t.name: t for t in (tools or [])}

    def schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]

    def run(self, name: str, arguments: dict) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"unknown tool: {name}"}
        try:
            return tool.run(**arguments)
        except Exception as exc:  # noqa: BLE001 - goes back to the LLM as the tool result either way
            return {"error": str(exc)}

    def __bool__(self) -> bool:
        return bool(self._tools)
