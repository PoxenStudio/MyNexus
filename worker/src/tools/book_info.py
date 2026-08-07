from grpc_client import CoreApiClient
from tools.base import BaseTool


class BookInfoTool(BaseTool):
    """Answers questions about a specific book's basic info/summary — author,
    publisher, category, tags, the whole-book summary, and each chapter's
    summary (everything a book record carries — see models.Book /
    ChapterInfo). This is what chapter/whole-book summary questions
    ("这本书讲了什么"/"第三章讲了什么"/"作者是谁") should hit: those
    summaries are already generated text sitting in the DB, so answering
    from them directly is both cheaper and more faithful than re-deriving an
    answer from noisy chunk-level RAG retrieval. Worker never touches Core
    API's database directly (see .claude/memory/mynexus_m2_decisions.md), so
    this calls the CoreApiService.GetBookInfo RPC instead of querying
    anything locally."""

    def __init__(self, core_api: CoreApiClient) -> None:
        self.core_api = core_api

    @property
    def name(self) -> str:
        return "get_book_info"

    @property
    def description(self) -> str:
        return (
            "查询某本书的基础信息与摘要：书名、作者、出版社、分类、标签、全书总结，"
            "以及每一章的标题和章节摘要。适用于回答“这本书讲了什么”“作者是谁”“出版社是谁”"
            "“第几章讲了什么”“帮我总结一下这本书/这一章”这类问题——这些内容已经生成好"
            "存在库里，应直接引用，而不是从原文片段里现推。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "书名或书名关键词（也可匹配作者），用于在书库中查找对应的书籍。",
                }
            },
            "required": ["query"],
        }

    def run(self, query: str) -> dict:
        books = self.core_api.get_book_info(query)
        if books is None:
            return {"error": "failed to reach core-api for book info"}
        if not books:
            return {"error": f"no book found matching {query!r}"}
        return {"books": books}
