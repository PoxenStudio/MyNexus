import json
import logging
import re
from typing import Iterator

from config import WorkerConfig, load_config
from nodes.factory import get_llm
from pipelines import chat_memory
from pipelines.fulltext import confirm_in_chapters
from pipelines.retrieval import RetrievalPipeline
from skills.catalog import builtin_skill_tools
from tools.book_info import BookInfoTool
from tools.library_stats import LibraryStatsTool
from tools.list_chapters import ListChaptersTool
from tools.mindmap import MindmapTool
from tools.read_chapter import ReadChapterTool
from tools.registry import ToolRegistry
from tools.search_by_chapters import SearchByChaptersTool
from tools.semantic_search import SemanticSearchTool

logger = logging.getLogger(__name__)

_CITED_RE = re.compile(r"\[(\d+)\]")


def _extract_cited_indices(answer: str) -> set[int]:
    return {int(m.group(1)) for m in _CITED_RE.finditer(answer)}

_ANSWER_RULES = (
    "回答规则：\n"
    "1. 书中事实（情节、人物言行、引句、章回内容）必须依据参考材料，并用 [编号] 标注来源；"
    "禁止编造引句或书中未出现的细节。\n"
    "2. 对材料的解释允许使用你的通用知识，例如古地名/古称对应今天的何地、字词释义、"
    "历史背景、名物常识；使用通用知识的部分不要标注 [编号]，并与书中依据区分清楚。\n"
    "3. 若材料已出现问题所问的对象但未直接给出答案（例如只出现古地名而未写今址），"
    "应结合通用知识把问题答完整，不得仅以“片段未说明”作答。\n"
    "4. 只有参考材料与通用知识都无法支撑时（如问某具体情节而书中确无相关内容），"
    "才如实说明未找到。\n"
)

_SYSTEM_PROMPT_TEMPLATE = (
    "你是一个书籍知识库问答助手。下面提供了与问题相关的参考材料，请据此回答用户问题。\n"
    + _ANSWER_RULES
    + "\n参考材料：\n{context}"
)


def _build_plain_context(chunks: list[dict], fulltext_snippets: list[dict]) -> str:
    parts = [f"[{i + 1}] {c['content']}" for i, c in enumerate(chunks)]
    idx = len(chunks)
    for snip in fulltext_snippets:
        idx += 1
        parts.append(f"[{idx}]（《{snip['title']}》全文定位）{snip['text']}")
    return "\n\n".join(parts)


def _memory_section(summary: str) -> str:
    summary = (summary or "").strip()
    if not summary:
        return ""
    return "\n\n## Conversation Memory\n" + summary


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
    "- 生成思维导图/知识图谱/概念图 → generate_mindmap（必须先调用 semantic_search/search_by_chapters/read_chapter 收集证据，再据证据编写 markdown；历史对话中已有充分证据时可直接生成）\n"
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
                MindmapTool(),
                *builtin_skill_tools(),
            ]
        )

    def answer(
        self,
        messages: list[dict],
        book_ids: list[str] | None = None,
        top_k: int = 10,
        memory_summary: str = "",
        memory_message_count: int = 0,
        older_messages: list[dict] | None = None,
    ) -> Iterator[dict]:
        window = self.config.chat_history_window
        if window and len(messages) > window:
            logger.info("chat history defensive truncation: %d -> %d", len(messages), window)
            messages = messages[-window:]

        active_summary = memory_summary or ""
        if older_messages and self.config.chat_memory_enabled:
            try:
                compressed = chat_memory.maybe_compress(self.llm.call, active_summary, older_messages)
            except Exception:
                logger.exception("memory compression failed, continuing with existing summary")
                compressed = None
            if compressed:
                new_summary, usage = compressed
                new_count = memory_message_count + len(older_messages)
                logger.info(
                    "memory compressed: older=%d cursor %d -> %d summary_len=%d",
                    len(older_messages), memory_message_count, new_count, len(new_summary),
                )
                yield {"type": "memory_update", "summary": new_summary, "message_count": new_count}
                self._report_memory_usage(usage, book_ids)
                active_summary = new_summary

        tool_results: list[dict] = []
        citations: list[dict] = []
        working = list(messages)
        active_skill: dict | None = None
        mindmap_emitted = False

        for _ in range(self.config.chat_max_tool_rounds):
            tool_call = self._decide_tool(working, active_skill, book_ids, active_summary)
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

            if name == "generate_mindmap" and not scope_error and "error" not in result:
                logger.info(
                    "mindmap tool ok: title=%s nodes=%s prior_citations=%d",
                    result.get("title"),
                    (result.get("stats") or {}).get("node_count"),
                    len(citations),
                )
                yield {"type": "tool_result", "tool_name": name, "result": result}
                tool_results.append(
                    {
                        "tool": name,
                        "arguments": {"title": result.get("title")},
                        "result": {
                            "type": "mindmap",
                            "title": result.get("title"),
                            "rendered": True,
                            "note": "思维导图已渲染给用户，最终回答中不要重复输出 markdown 原文",
                        },
                    }
                )
                mindmap_emitted = True
                break

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

        if mindmap_emitted:
            logger.info("mindmap emitted, streaming companion answer with %d citations", len(citations))
            yield from self._answer_from_tools(
                messages, tool_results, citations, active_skill, mindmap=True,
                memory_summary=active_summary,
            )
            return

        # Full-text confirmation for chunk-level tool evidence too
        # (semantic_search/search_by_chapters): like ReadAny's fallbackSearch,
        # locate the question's salient terms in the complete chapter text.
        # Skip when read_chapter already pulled full chapters.
        question = messages[-1]["content"] if messages else ""
        called_tools = {r["tool"] for r in tool_results}
        if (
            question
            and not active_skill
            and (called_tools & {"semantic_search", "search_by_chapters"})
            and "read_chapter" not in called_tools
        ):
            candidates: list[dict] = []
            seen_ft: set[str] = set()
            for c in citations:
                cid = c.get("chapter_id")
                if not cid or cid in seen_ft:
                    continue
                seen_ft.add(cid)
                candidates.append({"book_id": c["book_id"], "chapter_id": cid})
                if len(candidates) >= 8:
                    break
            if candidates:
                try:
                    ft = confirm_in_chapters(self.retrieval.core_api, question, candidates)
                except Exception:
                    ft = []
                    logger.exception("fulltext confirmation failed in tool path")
                if ft:
                    logger.info("tool path fulltext confirmed: %d snippets", len(ft))
                    tool_results.append(
                        {
                            "tool": "fulltext_confirm",
                            "arguments": {"query": question},
                            "result": {
                                "snippets": [
                                    {"chapter": s["title"], "terms": s["terms"], "text": s["text"]}
                                    for s in ft
                                ]
                            },
                        }
                    )
                    citations.extend(
                        {
                            "chunk_id": "",
                            "chapter_id": s["chapter_id"],
                            "book_id": s["book_id"],
                            "score": 1.0,
                            "content": f"《{s['title']}》全文定位：{'、'.join(s['terms'])}",
                        }
                        for s in ft
                    )

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
            yield from self._answer_from_tools(
                messages, tool_results, citations, active_skill, memory_summary=active_summary
            )
            return

        question = messages[-1]["content"] if messages else ""
        chunks = self.retrieval.search(question, book_ids=book_ids, top_k=top_k)
        # Drop chunks from cover/扉页/目录-style near-empty chapters that
        # occasionally survive semantic ranking.
        chunks = [c for c in chunks if len((c.get("content") or "").strip()) >= 30]

        # Full-text confirmation over complete chapter text (like ReadAny's
        # fallbackSearch): chunks are fixed-size windows, so rare proper nouns
        # can land on boundaries or lose surrounding context. Candidate
        # chapters come from chunk hits in score order — no extra broad scan.
        candidate_chapters: list[dict] = []
        seen_chapters: set[str] = set()
        for c in chunks:
            if not c.get("chapter_id") or c["chapter_id"] in seen_chapters:
                continue
            seen_chapters.add(c["chapter_id"])
            candidate_chapters.append({"book_id": c["book_id"], "chapter_id": c["chapter_id"]})
            if len(candidate_chapters) >= 8:
                break
        fulltext_snippets: list[dict] = []
        if candidate_chapters:
            try:
                fulltext_snippets = confirm_in_chapters(
                    self.retrieval.core_api, question, candidate_chapters
                )
            except Exception:
                logger.exception("fulltext confirmation failed, continuing with chunks only")

        citations = [
            {
                "chunk_id": c["id"],
                "chapter_id": c["chapter_id"],
                "book_id": c["book_id"],
                "score": c["score"],
                "content": c["content"][:200],
            }
            for c in chunks
        ]
        citations.extend(
            {
                "chunk_id": "",
                "chapter_id": s["chapter_id"],
                "book_id": s["book_id"],
                "score": 1.0,
                "content": f"《{s['title']}》全文定位：{'、'.join(s['terms'])}",
            }
            for s in fulltext_snippets
        )

        context = _build_plain_context(chunks, fulltext_snippets)
        system_message = {
            "role": "system",
            "content": _SYSTEM_PROMPT_TEMPLATE.format(context=context or "（无相关片段）")
            + _memory_section(active_summary),
        }
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
        logger.info(
            "plain RAG: answer cites %d/%d contexts (chunks=%d fulltext=%d)",
            len(used), len(citations), len(chunks), len(fulltext_snippets),
        )

        yield {"type": "citations", "citations": citations}

    def _decide_tool(
        self,
        messages: list[dict],
        active_skill: dict | None = None,
        book_ids: list[str] | None = None,
        memory_summary: str = "",
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
        decision_messages = [
            {"role": "system", "content": decision_prompt + _memory_section(memory_summary)}
        ] + messages
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

    def _report_memory_usage(self, usage, book_ids: list[str] | None) -> None:
        # Fire-and-forget：压缩 token 记账失败不得影响问答主流程
        if not usage or getattr(usage, "total_tokens", 0) <= 0:
            return
        try:
            self.retrieval.core_api.report_token_usage(
                task_id="",
                book_id=(book_ids[0] if book_ids else ""),
                task_type="chat",
                llm_provider=usage.provider,
                llm_model=usage.model,
                call_site="chat.memory_compress",
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
        except Exception:
            logger.exception("report memory compression token usage failed")

    def _answer_from_tools(
        self,
        messages: list[dict],
        tool_results: list[dict],
        citations: list[dict],
        active_skill: dict | None = None,
        mindmap: bool = False,
        memory_summary: str = "",
    ) -> Iterator[dict]:
        """Streams the final answer from accumulated tool results (single- or multi-round)."""
        context = "\n\n".join(
            f"[{r['tool']}({json.dumps(r['arguments'], ensure_ascii=False)})]\n"
            + json.dumps(r["result"], ensure_ascii=False)
            for r in tool_results
        )
        mindmap_instructions = ""
        if mindmap:
            mindmap_instructions = (
                "\n\n思维导图已经作为独立可视化卡片渲染给用户，不要重复输出其 markdown 原文。"
                "请用简短文字（可用小标题或表格）介绍图的主要分支与组织逻辑，"
                "并在结尾用一两句话给出后续可细化方向（如聚焦某个分支展开）。"
            )
        skill_instructions = ""
        if active_skill:
            skill_instructions = (
                f"\n\n当前任务流程：{active_skill['name']} ({active_skill['id']}, "
                f"v{active_skill['version']})\n"
                f"任务参数：{json.dumps(active_skill['arguments'], ensure_ascii=False)}\n"
                f"执行指引：{active_skill['prompt']}\n"
                "请遵循该流程完成回答。"
            )
        system_message = {
            "role": "system",
            "content": (
                "你是一个书籍知识库问答助手。已经为你查询到以下多组数据（按工具调用分组），"
                "请据此直接回答用户问题，不需要标注引用编号；"
                "如果用户问的是总结类问题，可以直接引用其中的总结/摘要内容作答。\n"
                + _ANSWER_RULES
                + "\n工具数据：\n"
                + context
                + skill_instructions
                + mindmap_instructions
                + _memory_section(memory_summary)
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
