import json
import logging
import re
from typing import Iterator

from config import WorkerConfig, load_config
from nodes.factory import get_llm
from pipelines.retrieval import RetrievalPipeline
from skills.catalog import builtin_skill_tools
from tools.book_info import BookInfoTool
from tools.library_stats import LibraryStatsTool
from tools.list_chapters import ListChaptersTool
from tools.read_chapter import ReadChapterTool
from tools.registry import ToolRegistry
from tools.search_by_chapters import SearchByChaptersTool
from tools.semantic_search import SemanticSearchTool

logger = logging.getLogger(__name__)

_CITED_RE = re.compile(r"\[(\d+)\]")


def _extract_cited_indices(answer: str) -> set[int]:
    return {int(m.group(1)) for m in _CITED_RE.finditer(answer)}

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
    "- 章节正文/概述/人物关系 → read_chapter\n"
    "- 跨章节的情节脉络/时间线/人物经历/主题演变 → search_by_chapters\n"
    "- 按语义找观点/定位段落/跨书检索 → semantic_search\n"
    "- 解释书中概念 → skill_concept_explainer\n"
    "- 分析作者主张、证据或论证结构 → skill_argument_analyzer\n"
    "- 追踪人物关系与发展 → skill_character_tracker\n"
    "- 收集原文引句 → skill_quote_collector\n"
    "- 生成预习、复习或讨论指南 → skill_reading_guide\n"
    "Skill 是任务流程指引，不是数据来源；选中后再调用必要的数据工具。一个回合只启用一个 Skill。\n"
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
        self.skill_tool_names = {tool.name for tool in builtin_skill_tools()}
        self.tools = ToolRegistry(
            [
                LibraryStatsTool(self.retrieval.core_api),
                BookInfoTool(self.retrieval.core_api),
                ListChaptersTool(self.retrieval.core_api),
                ReadChapterTool(self.retrieval.core_api),
                SearchByChaptersTool(self.retrieval),
                SemanticSearchTool(self.retrieval),
                *builtin_skill_tools(),
            ]
        )

    def answer(
        self, messages: list[dict], book_ids: list[str] | None = None, top_k: int = 10
    ) -> Iterator[dict]:
        tool_results: list[dict] = []
        citations: list[dict] = []
        working = list(messages)
        active_skill: dict | None = None

        for _ in range(self.config.chat_max_tool_rounds):
            tool_call = self._decide_tool(working, active_skill, book_ids)
            if tool_call is None:
                break
            name, arguments = tool_call
            arguments, scope_error = self._apply_book_scope(name, arguments, book_ids)
            if scope_error:
                result = {"error": scope_error}
            else:
                result = self.tools.run(name, arguments)
            if name == "get_book_info" and book_ids and not scope_error:
                allowed_ids = set(book_ids)
                result["books"] = [book for book in result.get("books", []) if book.get("book_id") in allowed_ids]
                if not result["books"] and "error" not in result:
                    result["error"] = "no book found within the current chat scope"
            citations.extend(result.pop("__citations", []) or [])
            skill_activation = result.pop("__skill__", None)
            if skill_activation:
                active_skill = skill_activation
                working = working + [
                    {"role": "assistant", "content": f"[已启用任务流程 {active_skill['name']}]"},
                    {
                        "role": "user",
                        "content": "请按当前任务流程继续，必要时调用数据工具获取书籍证据。",
                    },
                ]
            else:
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

        if active_skill and not citations:
            question = messages[-1]["content"] if messages else ""
            results = self.retrieval.search(question, book_ids=book_ids, top_k=top_k)
            citations.extend(
                {
                    "chunk_id": result["id"],
                    "chapter_id": result["chapter_id"],
                    "book_id": result["book_id"],
                    "score": result["score"],
                    "content": result["content"][:200],
                }
                for result in results
            )
            tool_results.append(
                {
                    "tool": "semantic_search",
                    "arguments": {"query": question, "book_ids": book_ids},
                    "result": {"results": results},
                }
            )

        if tool_results or active_skill:
            yield from self._answer_from_tools(messages, tool_results, citations, active_skill)
            return

        question = messages[-1]["content"] if messages else ""
        citations = self.retrieval.search(question, book_ids=book_ids, top_k=top_k)

        context = "\n\n".join(f"[{i + 1}] {c['content']}" for i, c in enumerate(citations))
        system_message = {"role": "system", "content": _SYSTEM_PROMPT_TEMPLATE.format(context=context or "（无相关片段）")}
        llm_messages = [system_message] + messages

        answer_chunks = []
        try:
            for delta in self.llm.process(llm_messages, call_site="qa.plain_answer"):
                answer_chunks.append(delta)
                yield {"type": "delta", "content": delta}
        except Exception as exc:
            logger.exception("qa plain answer stream failed")
            yield {"type": "delta", "content": f"\n\n⚠️ {exc}"}
            return

        answer_text = "".join(answer_chunks)
        used = _extract_cited_indices(answer_text)
        logger.info("plain RAG: answer cites %d/%d top-k chunks", len(used), len(citations))

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

    def _decide_tool(
        self,
        messages: list[dict],
        active_skill: dict | None = None,
        book_ids: list[str] | None = None,
    ) -> tuple[str, dict] | None:
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
        decision_prompt = _TOOL_DECISION_PROMPT
        excluded_names: set[str] = set()
        if book_ids:
            decision_prompt += (
                "\n本轮允许访问的 book_ids 为："
                f"{json.dumps(book_ids, ensure_ascii=False)}。工具参数不得指定此范围之外的书籍。"
            )
        if active_skill:
            decision_prompt += (
                "\n当前已启用任务流程："
                f"{active_skill['name']}（{active_skill['id']}）。\n"
                f"流程指引：{active_skill['prompt']}\n"
                f"参数：{json.dumps(active_skill['arguments'], ensure_ascii=False)}\n"
                "不要再次选择其他 Skill；如需证据，只调用合适的数据工具。"
            )
            excluded_names = self.skill_tool_names
        decision_messages = [{"role": "system", "content": decision_prompt}] + messages
        try:
            result = self.llm.call(decision_messages, tools=self.tools.schemas(excluded_names))
        except Exception as exc:  # noqa: BLE001 - fall through to normal RAG on any failure here
            logger.warning("tool-decision call failed, falling back to plain RAG: %s", exc)
            return None
        calls = result.get("tool_calls") or []
        if not calls:
            return None
        call = calls[0]
        return call["name"], call["arguments"]

    def _apply_book_scope(
        self, name: str, arguments: dict, book_ids: list[str] | None
    ) -> tuple[dict, str | None]:
        if not book_ids:
            return arguments, None

        allowed_ids = set(book_ids)
        scoped_arguments = dict(arguments)
        book_id = scoped_arguments.get("book_id")
        if book_id and book_id not in allowed_ids:
            return scoped_arguments, "book_id is outside the current chat scope"

        requested_book_ids = scoped_arguments.get("book_ids")
        if requested_book_ids:
            if not set(requested_book_ids).issubset(allowed_ids):
                return scoped_arguments, "book_ids contain values outside the current chat scope"
        elif name in self.skill_tool_names or name in {"semantic_search", "search_by_chapters"}:
            scoped_arguments["book_ids"] = list(book_ids)
        return scoped_arguments, None

    def _answer_from_tools(
        self,
        messages: list[dict],
        tool_results: list[dict],
        citations: list[dict],
        active_skill: dict | None = None,
    ) -> Iterator[dict]:
        """Streams the final answer from accumulated tool results (single- or multi-round)."""
        context = "\n\n".join(
            f"[{r['tool']}({json.dumps(r['arguments'], ensure_ascii=False)})]\n"
            + json.dumps(r["result"], ensure_ascii=False)
            for r in tool_results
        )
        skill_instructions = ""
        if active_skill:
            skill_instructions = (
                f"\n\n当前任务流程：{active_skill['name']} ({active_skill['id']}, "
                f"v{active_skill['version']})\n"
                f"任务参数：{json.dumps(active_skill['arguments'], ensure_ascii=False)}\n"
                f"执行指引：{active_skill['prompt']}\n"
                "请遵循该流程完成回答，并仅依据下方工具数据提供书籍事实。"
            )
        system_message = {
            "role": "system",
            "content": (
                "你是一个书籍知识库问答助手。已经为你查询到以下多组数据（按工具调用分组），"
                "请据此直接回答用户问题，不需要标注引用编号；"
                "如果用户问的是总结类问题，可以直接引用其中的总结/摘要内容作答；"
                "如果工具结果不足以完整回答，请如实说明信息边界（例如只读了部分章节）：\n"
                + context
                + skill_instructions
            ),
        }
        llm_messages = [system_message] + messages
        try:
            for delta in self.llm.process(llm_messages, call_site="qa.tool_answer"):
                yield {"type": "delta", "content": delta}
        except Exception as exc:
            logger.exception("qa tool answer stream failed")
            yield {"type": "delta", "content": f"\n\n⚠️ {exc}"}
            return
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
