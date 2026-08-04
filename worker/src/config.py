import os
from dataclasses import dataclass, field

import yaml

DEFAULT_CONFIG_PATH = "./config/config.yaml"


@dataclass
class WorkerConfig:
    port: int = 8001
    embedding_provider: str = "openai"
    llm_provider: str = "openai"
    vector_store: str = "chroma"
    max_concurrent_tasks: int = 1
    raw: dict = field(default_factory=dict)


def load_config() -> WorkerConfig:
    path = os.getenv("MYNEXUS_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    raw: dict = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    cfg = WorkerConfig(raw=raw)
    cfg.port = int(os.getenv("PORT", raw.get("worker", {}).get("port", cfg.port)))
    cfg.embedding_provider = raw.get("embedding", {}).get("provider", cfg.embedding_provider)
    cfg.llm_provider = raw.get("llm", {}).get("provider", cfg.llm_provider)
    cfg.vector_store = raw.get("storage", {}).get("vector_store", cfg.vector_store)
    cfg.max_concurrent_tasks = raw.get("worker", {}).get(
        "max_concurrent_tasks", cfg.max_concurrent_tasks
    )
    return cfg
