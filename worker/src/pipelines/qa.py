from typing import Iterator

from config import WorkerConfig, load_config
from nodes.factory import get_llm
from pipelines.retrieval import RetrievalPipeline

_SYSTEM_PROMPT_TEMPLATE = (
    "你是一个书籍知识库问答助手。请仅根据下面提供的参考片段回答用户问题，"
    "并在回答中用 [编号] 标注引用来源；如果参考片段中没有答案，请如实说明未找到相关内容。\n\n"
    "参考片段：\n{context}"
)


class QAPipeline:
    """Retrieve -> build prompt -> stream LLM answer -> emit citations.

    Yields dict events: {"type": "delta", "content": str} for each streamed
    token, followed by exactly one {"type": "citations", "citations": [...]}."""

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or load_config()
        self.retrieval = RetrievalPipeline(self.config)
        self.llm = get_llm(self.config)

    def answer(
        self, messages: list[dict], book_ids: list[str] | None = None, top_k: int = 5
    ) -> Iterator[dict]:
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
