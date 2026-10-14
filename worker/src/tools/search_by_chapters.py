from pipelines.retrieval import RetrievalPipeline
from tools.base import BaseTool

_CHUNKS_TOKEN_BUDGET = 4000
_MIN_SNIPPET_CHARS = 100


class SearchByChaptersTool(BaseTool):
    """Two-stage cross-chapter retrieval exposed to the chat LLM: routes the
    query to candidate chapters by aggregated chunk scores, then re-ranks
    real passages only within those chapters. Global flat retrieval
    (semantic_search) spreads its top-k across whichever chunks score well
    individually, so a question spanning ten chapters ("小沛争夺的时间线")
    gets swamped by single-chapter near-misses ("争夺" matching an unrelated
    duel) — chapter routing keeps the coverage where the theme actually
    lives."""

    def __init__(self, retrieval: RetrievalPipeline) -> None:
        self.retrieval = retrieval

    @property
    def name(self) -> str:
        return "search_by_chapters"

    @property
    def description(self) -> str:
        return (
            "面向跨章节主题的两阶段检索：先按内容定位相关章节，再只在这些章节内检索原文片段。"
            "适用于：情节时间线/脉络梳理、人物经历追踪、主题演变这类答案分散在多个章节的问题。"
            "单章节事实查询或按语义找观点请用 semantic_search。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索 query，描述要梳理的主题/脉络。"},
                "chapter_top_n": {"type": "integer", "default": 8, "description": "定位的候选章节数，默认 8。"},
                "top_k": {"type": "integer", "default": 10, "description": "返回片段条数，默认 10。"},
                "book_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "限定检索范围的书籍 id 列表，缺省为整个书库。",
                },
            },
            "required": ["query"],
        }

    def run(
        self,
        query: str,
        chapter_top_n: int = 8,
        top_k: int = 10,
        book_ids: list[str] | None = None,
    ) -> dict:
        try:
            chunks, chapters = self.retrieval.search_by_chapter_route(
                query, book_ids=book_ids, chapter_top_n=chapter_top_n, top_k=top_k
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the LLM as the tool result
            return {"error": f"chapter-routed search failed: {exc}"}

        if not chunks:
            return {
                "results": [],
                "routed_chapters": [],
                "returned": 0,
                "hint": "no relevant chapters found; try semantic_search instead",
            }

        snippets, used = [], 0
        for r in chunks:
            content = r["content"]
            budget = _CHUNKS_TOKEN_BUDGET - used
            if budget * 4 < _MIN_SNIPPET_CHARS:
                break
            if len(content) > budget * 4:
                content = content[: budget * 4]
            used += len(content) // 4
            snippets.append(
                {
                    "chunk_id": r["id"],
                    "book_id": r["book_id"],
                    "chapter_id": r["chapter_id"],
                    "content": content,
                    "score": round(r["score"], 4),
                    "start_offset": r["start_offset"],
                    "end_offset": r["end_offset"],
                    "truncated": len(content) < len(r["content"]),
                }
            )
        return {
            "routed_chapters": [
                {
                    "chapter_id": c["chapter_id"],
                    "book_id": c["book_id"],
                    "score": round(c["score"], 4),
                    "summary": c["summary"],
                }
                for c in chapters
            ],
            "results": snippets,
            "returned": len(snippets),
            "__citations": [
                {
                    "chunk_id": s["chunk_id"],
                    "chapter_id": s["chapter_id"],
                    "book_id": s["book_id"],
                    "score": s["score"],
                    "content": s["content"][:200],
                    "start_offset": s["start_offset"],
                    "end_offset": s["end_offset"],
                }
                for s in snippets
            ],
        }
