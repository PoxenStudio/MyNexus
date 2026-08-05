---
name: mynexus-m3-decisions
description: MyNexus M3 (retrieval/QA) architecture decisions — vector store choice, ID ownership, hybrid search approach
metadata:
  type: project
---

M3 implements chunking, embedding, hybrid search, and streaming RAG chat with citations (docs/开发技术文档.md §10.4). Key decisions:

**ChromaDB is the default vector store (`storage.vector_store: chroma`), NOT the numpy-based local store.**
Mid-M3 this went back and forth: first dropped ChromaDB for `simple_store.py` (numpy brute-force cosine + JSON file) reasoning that its dependency tree (onnxruntime, grpc, kubernetes client, opentelemetry) blew a "Worker capped at 512MB" budget. The user corrected this: NAS devices typically have 4GB+ RAM, so 512MB was an arbitrary number copied into docker-compose, not a real requirements-doc constraint — and separately pointed out the numpy/JSON approach doesn't scale at all (reloads and re-parses the *entire* JSON file into memory and does a full linear scan on every single query; at tens of thousands of books this is both a memory and a latency disaster, unlike ChromaDB's HNSW index + SQLite persistence which never needs the full corpus in memory). Implemented `worker/src/vector_store/chroma_store.py` (`chromadb.PersistentClient`, `hnsw:space: cosine`) as the real default; bumped Worker's docker-compose memory limit to 1536M. `simple_store.py` is kept as the `vector_store: local` fallback for genuinely tiny/constrained setups only — both implement `BaseVectorStore`, dispatched in `nodes/factory.py::get_vector_store`. Documented in docs/系统设计文档.md §3.4.
Why it matters: don't re-litigate this back to "avoid Chroma for memory reasons" — that reasoning was checked and rejected. If a future memory-budget concern comes up, it needs a real NAS spec citation, not an assumed number.
~~Known remaining gap: hybrid search's BM25/keyword side still loads the full candidate set and rebuilds a `rank_bm25` index per query~~ **Resolved 2026-08-05 for Postgres only** — see [[mynexus_keyword_search_gin]]. SQLite deployments (small-scale/trial only) still use the original in-process BM25 pass unchanged.

**Hybrid search = vector cosine (weight 0.6) + BM25 keyword (weight 0.4), fused by weighted sum.**
`rank_bm25` (tiny, pure-Python, already depends only on numpy) does the keyword side. Degrades gracefully to keyword-only if the embedding call throws (e.g. no API key configured) — see `RetrievalPipeline._vector_scores`'s try/except — so search stays usable without any embedding provider configured. CJK tokenization for BM25 is a crude regex (`[A-Za-z0-9]+|[一-鿿]`, i.e. each CJK character is its own token) rather than a real segmenter like jieba — again a dependency-weight tradeoff.

**"Token count" is a character-count approximation, not a real tokenizer.**
`nodes/splitters/token_splitter.py` treats `chunk_size`/`chunk_overlap` config values as character counts directly (`CHARS_PER_TOKEN = 1.0`). No `tiktoken` dependency. Fine for CJK-heavy text (~1 char ≈ 1 token); over-counts for English. Swap in a real tokenizer in `TokenSplitter` if/when precise chunk sizing starts to matter.

**Chapter and chunk IDs are assigned by Worker, not Core API.**
Extends the M2 pattern ([[mynexus_m2_decisions]]): Worker generates `uuid4()` for each `ParsedChapter`/`Chunk` during `parse_and_clean`/`TokenSplitter.process`, sends them in the `/internal/tasks/{id}/complete` callback, and Core API's `SaveChapters`/`SaveChunks` use the *given* IDs instead of generating their own. This is required because Worker needs a chapter_id to tag chunks with *before* Core API has ever seen those chapters (single pipeline run, single completion callback — no mid-pipeline round trip to ask Core API for IDs).

**Chunk's `vector_id` is just the chunk's own ID.**
Both `ChromaStore` and `SimpleVectorStore` key records by `chunk.id`, so there's no separate ID space to track — `vector_id` in Core API's `chunks` table and the Chroma document ID are the same string. The callback payload (`ChunkMetaCallback.VectorID`) makes this explicit.

**Extended the M2 auth workaround to chat.** `chat_handler.go` also hardcodes `defaultUserID = "local-user"` (same constant, same file package) for session ownership — consistent with the M1/M2 decision to defer real auth to M4.

**Testing without real API keys**: `worker/tests/mock_openai_server.py` is a small stdlib-only HTTP server that fakes OpenAI's `/embeddings` (hash-based deterministic vectors) and `/chat/completions` (canned streamed reply) endpoints. Used to validate `OpenAIEmbedder`/`OpenAILLM` and the full ingest→search→chat loop end-to-end in dev without hitting real OpenAI. Point `embedding.openai.base_url` / `llm.openai.base_url` at `http://localhost:<port>/v1` to use it. See [[mynexus_worker_cli_testable]] and [[mynexus_macos_proxy_gotcha]] — the latter's fix (bypass proxy for local/LAN hosts) was generalized into `worker/src/util/http.py::urlopen`, now used by all outbound HTTP in worker (ingestion callbacks, embedders, LLMs), not just ingestion's Core API callbacks.
