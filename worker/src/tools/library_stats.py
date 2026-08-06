from grpc_client import CoreApiClient
from tools.base import BaseTool


class LibraryStatsTool(BaseTool):
    """Answers "how many books are in the system" / "how many are still
    processing" style questions. Worker never touches Core API's database
    directly (see .claude/memory/mynexus_m2_decisions.md), so this calls the
    CoreApiService.GetLibraryStats RPC instead of querying anything locally."""

    def __init__(self, core_api: CoreApiClient) -> None:
        self.core_api = core_api

    @property
    def name(self) -> str:
        return "get_library_stats"

    @property
    def description(self) -> str:
        return (
            "获取当前系统中的书籍统计信息：书籍总数，以及按状态"
            "（ready=已就绪, processing=处理中, pending=待处理, failed=失败）分类的数量。"
            "用于回答关于系统本身状态的问题（如“现在有多少本书”“有几本处理失败了”），"
            "而不是书籍内容问题。"
        )

    def run(self) -> dict:
        stats = self.core_api.get_library_stats()
        if stats is None:
            return {"error": "failed to reach core-api for library stats"}
        return stats
