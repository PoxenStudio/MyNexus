from pipelines.retrieval import RetrievalPipeline
from tools.base import BaseTool

_TOTAL_TOKEN_BUDGET = 4000
_MIN_SNIPPET_CHARS = 100


class SemanticSearchTool(BaseTool):
    """Cross-library semantic / keyword / hybrid chunk retrieval, exposed to
    the chat LLM as a tool. Complements the always-on RAG path by letting the
    model choose the retrieval mode and book scope explicitly (e.g. "按语义
    寻找观点" requests that should fan out across the whole library instead
    of being limited to the books the session was opened with)."""

    def __init__(self, retrieval: RetrievalPipeline) -> None:
        self.retrieval = retrieval

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return (
            "在书籍库中按语义或关键词检索相关片段。适用于：按语义寻找观点/说法、定位具体段落的出处、"
            "跨书检索同一主题。mode=hybrid 同时用语义和关键词（默认，效果最好）；"
            "mode=vector 纯语义；mode=bm25 纯关键词。不传 book_ids 时检索整个书库。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索 query，描述要寻找的观点/主题/说法。"},
                "mode": {"type": "string", "enum": ["hybrid", "vector", "bm25"], "default": "hybrid"},
                "top_k": {"type": "integer", "default": 5, "description": "返回条数，默认 5。"},
                "book_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "限定检索范围的书籍 id 列表，缺省为整个书库。",
                },
            },
            "required": ["query"],
        }

    def run(self, query: str, mode: str = "hybrid", top_k: int = 5, book_ids: list[str] | None = None) -> dict:
        vector_status = "ok"
        try:
            results = self.retrieval.search(query, book_ids=book_ids, top_k=top_k, score_threshold=0.3, mode=mode)
        except Exception as exc:  # noqa: BLE001 - surfaced to the LLM as the tool result
            return {"error": f"search failed: {exc}"}

        if mode in ("hybrid", "vector") and not results:
            vector_status = "embedding unavailable or no hits; try mode=bm25"

        snippets, used = [], 0
        for r in results:
            content = r["content"]
            budget = _TOTAL_TOKEN_BUDGET - used
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
            "results": snippets,
            "returned": len(snippets),
            "total": len(results),
            "vector_status": vector_status,
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
