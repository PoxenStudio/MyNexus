import json
from typing import Iterator

from config import WorkerConfig, load_config
from nodes.factory import get_llm
from pipelines.retrieval import RetrievalPipeline
from tools.library_stats import LibraryStatsTool
from tools.registry import ToolRegistry

_SYSTEM_PROMPT_TEMPLATE = (
    "你是一个书籍知识库问答助手。请仅根据下面提供的参考片段回答用户问题，"
    "并在回答中用 [编号] 标注引用来源；如果参考片段中没有答案，请如实说明未找到相关内容。\n\n"
    "参考片段：\n{context}"
)

# Only used for the tool-call decision step (see _decide_tool) — kept
# separate from _SYSTEM_PROMPT_TEMPLATE since that one always carries
# retrieved chunks, which the decision step deliberately skips (retrieval
# hasn't run yet at that point, and system-status questions wouldn't hit
# anything relevant in it anyway).
_TOOL_DECISION_PROMPT = (
    "你是一个书籍知识库问答助手，可以调用工具查询系统状态。"
    "如果用户问题是关于系统/书库本身状态的（例如书籍数量、处理进度等，而不是书籍内容），"
    "请调用合适的工具；否则不要调用任何工具，直接留空。"
)


class QAPipeline:
    """Retrieve -> build prompt -> stream LLM answer -> emit citations.

    Yields dict events: {"type": "delta", "content": str} for each streamed
    token, followed by exactly one {"type": "citations", "citations": [...]}."""

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.retrieval = RetrievalPipeline(self.config)
        self.llm = get_llm(self.config)
        # Reuses retrieval's CoreApiClient (one persistent channel — see
        # .claude/memory/mynexus_grpc_migration.md) rather than opening a
        # second one just for tools. Add new BaseTool subclasses here as the
        # assistant's system-status capabilities grow (see tools/base.py).
        self.tools = ToolRegistry([LibraryStatsTool(self.retrieval.core_api)])

    def answer(
        self, messages: list[dict], book_ids: list[str] | None = None, top_k: int = 5
    ) -> Iterator[dict]:
        if self.tools:
            tool_call = self._decide_tool(messages)
            if tool_call is not None:
                name, arguments = tool_call
                result = self.tools.run(name, arguments)
                yield from self._answer_from_tool(messages, result)
                return

        question = messages[-1]["content"] if messages else ""
        citations = self.retrieval.search(question, book_ids=book_ids, top_k=top_k)

        context = "\n\n".join(f"[{i + 1}] {c['content']}" for i, c in enumerate(citations))
        system_message = {"role": "system", "content": _SYSTEM_PROMPT_TEMPLATE.format(context=context or "（无相关片段）")}
        llm_messages = [system_message] + messages

        for delta in self.llm.process(llm_messages):
            yield {"type": "delta", "content": delta}

        yield {
            "type": "citations",
            "citations": [
                {
                    "chunk_id": c["id"],
                    "chapter_id": c["chapter_id"],
                    "book_id": c["book_id"],
                    "score": c["score"],
                    "content": c["content"][:200],
                }
                for c in citations
            ],
        }

    def _decide_tool(self, messages: list[dict]) -> tuple[str, dict] | None:
        """Single non-streaming call asking the model whether this turn needs
        a tool (see BaseLLM.call) — separate from the streaming call in
        answer() because a decision needs one structured response, not a
        token stream. Returns (name, arguments) for the first requested tool
        call, or None if the model chose to answer normally (the common
        case — this runs on every turn, so most calls are expected to fall
        through to the existing RAG path below).

        Never raises: a provider/network hiccup here shouldn't sink the
        whole chat turn, it just means this turn behaves as if no tools were
        offered.
        """
        decision_messages = [{"role": "system", "content": _TOOL_DECISION_PROMPT}] + messages
        try:
            result = self.llm.call(decision_messages, tools=self.tools.schemas())
        except Exception:  # noqa: BLE001 - fall through to normal RAG on any failure here
            return None
        calls = result.get("tool_calls") or []
        if not calls:
            return None
        call = calls[0]
        return call["name"], call["arguments"]

    def _answer_from_tool(self, messages: list[dict], result: dict) -> Iterator[dict]:
        """Streams the final answer once a tool result is in hand. No
        citations here — the answer comes from a system-status lookup, not
        retrieved book content, so there's nothing to cite (empty citations
        list, same event shape the RAG path emits)."""
        system_message = {
            "role": "system",
            "content": (
                "你是一个书籍知识库问答助手。已经为你查询到以下系统状态数据（JSON），"
                "请据此直接、简洁地回答用户问题，不需要标注引用编号：\n"
                + json.dumps(result, ensure_ascii=False)
            ),
        }
        llm_messages = [system_message] + messages
        for delta in self.llm.process(llm_messages):
            yield {"type": "delta", "content": delta}
        yield {"type": "citations", "citations": []}


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m pipelines.qa "这本书讲了什么" --path /tmp/vstest
    import argparse

    parser = argparse.ArgumentParser(description="Run the RAG QA pipeline against the local vector store.")
    parser.add_argument("question")
    parser.add_argument("--path", default="./data/vectorstore")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    cfg = load_config()
    cfg.vector_store_path = args.path
    for event in QAPipeline(cfg).answer([{"role": "user", "content": args.question}], top_k=args.top_k):
        if event["type"] == "delta":
            print(event["content"], end="", flush=True)
        else:
            print("\n\ncitations:")
            for c in event["citations"]:
                print(f"  [{c['chunk_id']}] score={c['score']:.3f} {c['content'][:60]!r}")
