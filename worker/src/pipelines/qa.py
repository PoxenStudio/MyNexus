import json
import logging
from typing import Iterator

from config import WorkerConfig, load_config
from nodes.factory import get_llm
from pipelines.retrieval import RetrievalPipeline
from tools.book_info import BookInfoTool
from tools.library_stats import LibraryStatsTool
from tools.list_chapters import ListChaptersTool
from tools.read_chapter import ReadChapterTool
from tools.registry import ToolRegistry
from tools.semantic_search import SemanticSearchTool

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = (
    "你是一个书籍知识库问答助手。请仅根据下面提供的参考片段回答用户问题，"
    "并在回答中用 [编号] 标注引用来源；如果参考片段中没有答案，请如实说明未找到相关内容。\n\n"
    "参考片段：\n{context}"
)

# Only used for the tool-call decision step (see _decide_tool) — kept
# separate from _SYSTEM_PROMPT_TEMPLATE since that one always carries
# retrieved chunks, which the decision step deliberately skips (retrieval
# hasn't run yet at that point, and system-status/book-info questions
# wouldn't hit anything relevant in it anyway).
_TOOL_DECISION_PROMPT = (
    "你是一个书籍知识库问答助手，可以调用工具查询系统状态、书籍基础信息、书籍章节结构与正文、"
    "或按语义检索内容片段。请按问题类型选择工具：\n"
    "- 系统/书库状态（数量、进度）→ get_library_stats\n"
    "- 书的元信息/已生成的总结 → get_book_info\n"
    "- 章节目录（决定读哪章）→ list_chapters\n"
    "- 章节正文/概述/人物关系/情节脉络 → read_chapter\n"
    "- 按语义找观点/定位段落/跨书检索 → semantic_search\n"
    "如果问题不在上述范围、或可通过对话历史直接回答，不要调用任何工具，直接留空。"
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
        # assistant's system-status/book-lookup capabilities grow (see
        # tools/base.py).
        self.tools = ToolRegistry(
            [
                LibraryStatsTool(self.retrieval.core_api),
                BookInfoTool(self.retrieval.core_api),
                ListChaptersTool(self.retrieval.core_api),
                ReadChapterTool(self.retrieval.core_api),
                SemanticSearchTool(self.retrieval),
            ]
        )

    def answer(
        self, messages: list[dict], book_ids: list[str] | None = None, top_k: int = 5
    ) -> Iterator[dict]:
        tool_results: list[dict] = []
        citations: list[dict] = []
        working = list(messages)

        for _ in range(self.config.chat_max_tool_rounds):
            tool_call = self._decide_tool(working)
            if tool_call is None:
                break
            name, arguments = tool_call
            result = self.tools.run(name, arguments)
            citations.extend(result.pop("__citations", []) or [])
            tool_results.append({"tool": name, "arguments": arguments, "result": result})
            working = working + [
                {"role": "assistant", "content": f"[已调用工具 {name}]"},
                {
                    "role": "user",
                    "content": (
                        f"工具 {name} 返回：\n{json.dumps(result, ensure_ascii=False)}\n"
                        "请根据以上工具结果继续回答，或调用其他工具获取更多上下文。"
                    ),
                },
            ]

        if tool_results:
            yield from self._answer_from_tools(messages, tool_results, citations)
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
        except Exception as exc:  # noqa: BLE001 - fall through to normal RAG on any failure here
            logger.warning("tool-decision call failed, falling back to plain RAG: %s", exc)
            return None
        calls = result.get("tool_calls") or []
        if not calls:
            return None
        call = calls[0]
        return call["name"], call["arguments"]

    def _answer_from_tools(
        self, messages: list[dict], tool_results: list[dict], citations: list[dict]
    ) -> Iterator[dict]:
        """Streams the final answer from accumulated tool results (single- or multi-round)."""
        context = "\n\n".join(
            f"[{r['tool']}({json.dumps(r['arguments'], ensure_ascii=False)})]\n"
            + json.dumps(r["result"], ensure_ascii=False)
            for r in tool_results
        )
        system_message = {
            "role": "system",
            "content": (
                "你是一个书籍知识库问答助手。已经为你查询到以下多组数据（按工具调用分组），"
                "请据此直接回答用户问题，不需要标注引用编号；"
                "如果用户问的是总结类问题，可以直接引用其中的总结/摘要内容作答；"
                "如果工具结果不足以完整回答，请如实说明信息边界（例如只读了部分章节）：\n"
                + context
            ),
        }
        llm_messages = [system_message] + messages
        for delta in self.llm.process(llm_messages):
            yield {"type": "delta", "content": delta}
        yield {"type": "citations", "citations": citations}


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
