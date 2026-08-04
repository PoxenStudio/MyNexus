import os
from dataclasses import dataclass, field

import yaml

DEFAULT_CONFIG_PATH = "./config/config.yaml"


@dataclass
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass
class SplitterConfig:
    chunk_size: int = 500
    chunk_overlap: int = 50
    strategy: str = "token"


@dataclass
class WorkerConfig:
    port: int = 8001
    max_concurrent_tasks: int = 1

    embedding_provider: str = "openai"
    embedding_openai: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="https://api.openai.com/v1", model="text-embedding-3-small")
    )
    embedding_ollama: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="http://localhost:11434", model="nomic-embed-text")
    )

    llm_provider: str = "openai"
    llm_openai: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    )
    llm_ollama: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(base_url="http://localhost:11434", model="llama3")
    )

    splitter: SplitterConfig = field(default_factory=SplitterConfig)

    # vector_store: chroma (default, HNSW-indexed, scales to large libraries) |
    # local (brute-force numpy + JSON, fine for a few thousand chunks / very
    # constrained devices only) — see docs/系统设计文档.md §3.4.
    vector_store: str = "chroma"
    vector_store_path: str = "./data/vectorstore"

    raw: dict = field(default_factory=dict)

    @property
    def active_embedder(self) -> ProviderConfig:
        return self.embedding_openai if self.embedding_provider == "openai" else self.embedding_ollama

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

    cfg.llm_provider = raw.get("llm", {}).get("provider", cfg.llm_provider)
    cfg.llm_openai = _provider(raw, "llm", "openai", cfg.llm_openai)
    cfg.llm_ollama = _provider(raw, "llm", "ollama", cfg.llm_ollama)

    splitter = raw.get("splitter", {})
    cfg.splitter = SplitterConfig(
        chunk_size=splitter.get("chunk_size", cfg.splitter.chunk_size),
        chunk_overlap=splitter.get("chunk_overlap", cfg.splitter.chunk_overlap),
        strategy=splitter.get("strategy", cfg.splitter.strategy),
    )

    cfg.vector_store = raw.get("storage", {}).get("vector_store", cfg.vector_store)
    cfg.vector_store_path = raw.get("storage", {}).get("vector_store_path", cfg.vector_store_path)

    if v := os.getenv("MYNEXUS_EMBEDDING_OPENAI_API_KEY"):
        cfg.embedding_openai.api_key = v
    if v := os.getenv("MYNEXUS_LLM_OPENAI_API_KEY"):
        cfg.llm_openai.api_key = v

    return cfg
