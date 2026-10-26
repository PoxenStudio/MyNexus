import logging
import os
from dataclasses import dataclass, field

import yaml

DEFAULT_CONFIG_PATH = "./config/config.yaml"

# LLM 请求超时（秒）：既用于建立连接/读取响应，也用作流式响应中途无有效内容的空闲超时。
LLM_TIMEOUT_MIN = 20
LLM_TIMEOUT_MAX = 1800
LLM_TIMEOUT_DEFAULT = 90


@dataclass
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass
class SplitterConfig:
    # chunk_size/chunk_overlap 单位为字符数（中文约等于 token 数）
    chunk_size: int = 150
    chunk_overlap: int = 30
    strategy: str = "token"


@dataclass
class WorkerConfig:
    port: int = 8001
    max_concurrent_tasks: int = 1

    embedding_provider: str = "local"
    embedding_openai: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="https://api.openai.com/v1", model="text-embedding-3-small")
    )
    embedding_ollama: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="http://localhost:11434", model="nomic-embed-text")
    )
    embedding_local_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_local_model_path: str = ""

    llm_provider: str = "openai"
    llm_openai: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    )
    llm_ollama: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="http://localhost:11434", model="llama3")
    )
    llm_openai_timeout: int = LLM_TIMEOUT_DEFAULT
    llm_ollama_timeout: int = LLM_TIMEOUT_DEFAULT
    llm_openai_chapter_token_budget: int = 30000

    splitter: SplitterConfig = field(default_factory=SplitterConfig)

    # vector_store: chroma (default, HNSW-indexed, scales to large libraries) |
    # local (brute-force numpy + JSON, fine for a few thousand chunks / very
    # constrained devices only) — see docs/系统设计文档.md §3.4.
    vector_store: str = "chroma"
    vector_store_path: str = "./data/vectorstore"

    # storage_database mirrors Core API's storage.database (sqlite | postgres).
    # RetrievalPipeline uses this to decide whether it can call Core API's
    # GIN-indexed /internal/search/keyword endpoint (postgres only) or must
    # fall back to its own in-process BM25 pass (sqlite — small-scale/trial
    # deployments only, see docs/系统设计文档.md).
    storage_database: str = "sqlite"

    # core_api_base_url is Worker's gRPC dial target for calling Core API back
    # (task progress/complete/fail, keyword search) — a bare "host:port"
    # authority (e.g. "core-api:9090" in Docker, "localhost:9090" locally),
    # NOT an "http://" URL. This is Core API's *gRPC* port (server.grpc_port
    # in core-api/internal/config/config.go), not its browser-facing HTTP
    # port. See .claude/memory/mynexus_grpc_migration.md.
    core_api_base_url: str = "localhost:9090"

    # cover_font_path optionally overrides util/cover_generator.py's font
    # resolution (see that module's doc comment for the full fallback
    # chain — this is checked first, before the shared data/fonts/ volume
    # and the font baked into the Worker image). Empty (the default) skips
    # straight to that fallback chain.
    cover_font_path: str = ""

    # debug_llm_logging mirrors Core API's debug.llm_logging (system settings
    # page, "打开调试日志"). When true, every LLM call
    # (nodes/llm/openai_llm.py, nodes/llm/ollama_llm.py) dumps its request
    # messages and full response text as a matched pair of files under the OS
    # temp dir — see util/debug_log.py. Off by default: request/response
    # bodies can contain book content and API responses, not something to
    # leave on disk in a default deployment.
    debug_llm_logging: bool = False

    # skip_backmatter_chapters mirrors Core API's summary.skip_backmatter_chapters
    # (system settings page, "生成章节总结时跳过书后参考书目及索引章节"). When
    # true (the default), parsers (nodes/parsers/*.py) drop chapters whose
    # cleaned title is an index/bibliography heading (see
    # util/chapter_title.py) instead of ingesting/summarizing them.
    skip_backmatter_chapters: bool = True

    # 会话工具调用最大轮数，达到后强制基于已积累上下文作答。
    chat_max_tool_rounds: int = 3

    # 发给 LLM 的最近 user/assistant 消息条数上限，core-api 已做窗口截断，此处为防御兜底。
    # 与 core-api 共用 config.yaml 的 chat.sliding_window_size 键。
    chat_history_window: int = 8

    # 滑出窗口的旧消息是否增量压缩为长期记忆摘要。
    chat_memory_enabled: bool = True

    retrieval_fusion: str = "weighted"
    retrieval_vector_weight: float = 0.6
    retrieval_keyword_weight: float = 0.4

    log_dir: str = ""
    log_level: str = "INFO"

    raw: dict = field(default_factory=dict)

    @property
    def active_embedder(self) -> ProviderConfig:
        if self.embedding_provider == "openai":
            return self.embedding_openai
        if self.embedding_provider == "ollama":
            return self.embedding_ollama
        return ProviderConfig(model=self.embedding_local_model)

    @property
    def active_llm(self) -> ProviderConfig:
        return self.llm_openai if self.llm_provider == "openai" else self.llm_ollama


def _provider(raw: dict, section: str, name: str, default: ProviderConfig) -> ProviderConfig:
    node = raw.get(section, {}).get(name, {})
    return ProviderConfig(
        api_key=node.get("api_key", default.api_key),
        base_url=node.get("base_url", default.base_url),
        model=node.get("model", default.model),
    )


def _clamp_llm_timeout(value, source: str, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning("%s=%r 不是合法整数，使用默认值 %ds", source, value, default)
        return default
    if timeout < LLM_TIMEOUT_MIN or timeout > LLM_TIMEOUT_MAX:
        clamped = min(max(timeout, LLM_TIMEOUT_MIN), LLM_TIMEOUT_MAX)
        logging.getLogger(__name__).warning(
            "%s=%d 超出允许范围 %d~%d，已调整为 %ds",
            source, timeout, LLM_TIMEOUT_MIN, LLM_TIMEOUT_MAX, clamped,
        )
        return clamped
    return timeout


def _llm_timeout_from_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return _clamp_llm_timeout(raw, name, default)


def load_config() -> WorkerConfig:
    path = os.getenv("MYNEXUS_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    raw: dict = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    cfg = WorkerConfig(raw=raw)
    cfg.port = int(os.getenv("PORT", raw.get("worker", {}).get("port", cfg.port)))
    cfg.max_concurrent_tasks = raw.get("worker", {}).get("max_concurrent_tasks", cfg.max_concurrent_tasks)

    cfg.embedding_provider = raw.get("embedding", {}).get("provider", cfg.embedding_provider)
    cfg.embedding_openai = _provider(raw, "embedding", "openai", cfg.embedding_openai)
    cfg.embedding_ollama = _provider(raw, "embedding", "ollama", cfg.embedding_ollama)
    cfg.embedding_local_model = raw.get("embedding", {}).get("local", {}).get("model", cfg.embedding_local_model)
    cfg.embedding_local_model_path = raw.get("embedding", {}).get("local", {}).get("model_path", cfg.embedding_local_model_path)

    cfg.llm_provider = raw.get("llm", {}).get("provider", cfg.llm_provider)
    cfg.llm_openai = _provider(raw, "llm", "openai", cfg.llm_openai)
    cfg.llm_ollama = _provider(raw, "llm", "ollama", cfg.llm_ollama)
    budget = int(raw.get("llm", {}).get("openai", {}).get("chapter_token_budget", cfg.llm_openai_chapter_token_budget))
    cfg.llm_openai_chapter_token_budget = min(max(budget, 5000), 50000) if budget > 0 else 0
    cfg.llm_openai_timeout = _clamp_llm_timeout(
        raw.get("llm", {}).get("openai", {}).get("timeout"),
        "llm.openai.timeout", cfg.llm_openai_timeout,
    )
    cfg.llm_ollama_timeout = _clamp_llm_timeout(
        raw.get("llm", {}).get("ollama", {}).get("timeout"),
        "llm.ollama.timeout", cfg.llm_ollama_timeout,
    )

    splitter = raw.get("splitter", {})
    cfg.splitter = SplitterConfig(
        chunk_size=splitter.get("chunk_size", cfg.splitter.chunk_size),
        chunk_overlap=splitter.get("chunk_overlap", cfg.splitter.chunk_overlap),
        strategy=splitter.get("strategy", cfg.splitter.strategy),
    )

    cfg.vector_store = raw.get("storage", {}).get("vector_store", cfg.vector_store)
    cfg.vector_store_path = raw.get("storage", {}).get("vector_store_path", cfg.vector_store_path)
    cfg.storage_database = raw.get("storage", {}).get("database", cfg.storage_database)
    cfg.core_api_base_url = raw.get("server", {}).get("internal_url", cfg.core_api_base_url)
    cfg.debug_llm_logging = raw.get("debug", {}).get("llm_logging", cfg.debug_llm_logging)
    cfg.skip_backmatter_chapters = raw.get("summary", {}).get(
        "skip_backmatter_chapters", cfg.skip_backmatter_chapters
    )
    cfg.cover_font_path = raw.get("cover", {}).get("font_path", cfg.cover_font_path)
    cfg.chat_max_tool_rounds = int(raw.get("chat", {}).get("max_tool_rounds", cfg.chat_max_tool_rounds))
    cfg.chat_history_window = int(raw.get("chat", {}).get("sliding_window_size", cfg.chat_history_window))
    cfg.chat_memory_enabled = raw.get("chat", {}).get("memory_enabled", cfg.chat_memory_enabled)

    retrieval = raw.get("retrieval", {})
    cfg.retrieval_fusion = retrieval.get("fusion", cfg.retrieval_fusion)
    cfg.retrieval_vector_weight = float(retrieval.get("vector_weight", cfg.retrieval_vector_weight))
    cfg.retrieval_keyword_weight = float(retrieval.get("keyword_weight", cfg.retrieval_keyword_weight))

    configured_log_dir = raw.get("storage", {}).get("log_dir", "")
    if configured_log_dir:
        cfg.log_dir = configured_log_dir
    elif os.getenv("MYNEXUS_IN_DOCKER", "").strip().lower() in ("1", "true", "yes", "on"):
        cfg.log_dir = "/data/logs"
    else:
        cfg.log_dir = "./data/logs"

    cfg.log_level = raw.get("debug", {}).get("log_level", cfg.log_level)

    if v := os.getenv("MYNEXUS_DEBUG_LLM_LOGGING"):
        cfg.debug_llm_logging = v.strip().lower() in ("1", "true", "yes", "on")

    if v := os.getenv("MYNEXUS_EMBEDDING_PROVIDER"):
        cfg.embedding_provider = v
    if v := os.getenv("MYNEXUS_EMBEDDING_OPENAI_API_KEY"):
        cfg.embedding_openai.api_key = v
    if v := os.getenv("MYNEXUS_EMBEDDING_OPENAI_BASE_URL"):
        cfg.embedding_openai.base_url = v
    if v := os.getenv("MYNEXUS_EMBEDDING_OPENAI_MODEL"):
        cfg.embedding_openai.model = v
    if v := os.getenv("MYNEXUS_EMBEDDING_OLLAMA_BASE_URL"):
        cfg.embedding_ollama.base_url = v
    if v := os.getenv("MYNEXUS_EMBEDDING_OLLAMA_MODEL"):
        cfg.embedding_ollama.model = v
    if v := os.getenv("MYNEXUS_EMBEDDING_LOCAL_MODEL"):
        cfg.embedding_local_model = v
    if v := os.getenv("MYNEXUS_EMBEDDING_LOCAL_MODEL_PATH"):
        cfg.embedding_local_model_path = v

    if v := os.getenv("MYNEXUS_LLM_PROVIDER"):
        cfg.llm_provider = v
    if v := os.getenv("MYNEXUS_LLM_OPENAI_API_KEY"):
        cfg.llm_openai.api_key = v
    if v := os.getenv("MYNEXUS_LLM_OPENAI_BASE_URL"):
        cfg.llm_openai.base_url = v
    if v := os.getenv("MYNEXUS_LLM_OPENAI_MODEL"):
        cfg.llm_openai.model = v
    if v := os.getenv("MYNEXUS_LLM_OLLAMA_BASE_URL"):
        cfg.llm_ollama.base_url = v
    if v := os.getenv("MYNEXUS_LLM_OLLAMA_MODEL"):
        cfg.llm_ollama.model = v
    cfg.llm_openai_timeout = _llm_timeout_from_env("MYNEXUS_LLM_OPENAI_TIMEOUT", cfg.llm_openai_timeout)
    cfg.llm_ollama_timeout = _llm_timeout_from_env("MYNEXUS_LLM_OLLAMA_TIMEOUT", cfg.llm_ollama_timeout)
    # In Docker, config.yaml's static value is "localhost:9090" for local dev,
    # but the worker container needs "core-api:9090"; docker-compose.yml sets
    # this env var explicitly for the worker service.
    if v := os.getenv("MYNEXUS_SERVER_INTERNAL_URL"):
        cfg.core_api_base_url = v
    if v := os.getenv("MYNEXUS_STORAGE_DATABASE"):
        cfg.storage_database = v
    if v := os.getenv("MYNEXUS_CHAT_SLIDING_WINDOW_SIZE"):
        cfg.chat_history_window = int(v)
    if v := os.getenv("MYNEXUS_CHAT_MEMORY_ENABLED"):
        cfg.chat_memory_enabled = v.strip().lower() in ("1", "true", "yes", "on")

    return cfg
