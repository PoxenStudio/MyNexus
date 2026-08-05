from config import WorkerConfig
from nodes.embedders.base_embedder import BaseEmbedder
from nodes.embedders.ollama_embedder import OllamaEmbedder
from nodes.embedders.openai_embedder import OpenAIEmbedder
from nodes.llm.base_llm import BaseLLM
from nodes.llm.ollama_llm import OllamaLLM
from nodes.llm.openai_llm import OpenAILLM
from vector_store.base_store import BaseVectorStore
from vector_store.chroma_store import ChromaStore
from vector_store.simple_store import SimpleVectorStore


def get_embedder(cfg: WorkerConfig) -> BaseEmbedder:
    if cfg.embedding_provider == "ollama":
        return OllamaEmbedder(cfg.embedding_ollama.base_url, cfg.embedding_ollama.model)
    provider = cfg.embedding_openai
    return OpenAIEmbedder(provider.api_key, provider.base_url, provider.model)


def get_llm(cfg: WorkerConfig) -> BaseLLM:
    if cfg.llm_provider == "ollama":
        return OllamaLLM(cfg.llm_ollama.base_url, cfg.llm_ollama.model, debug=cfg.debug_llm_logging)
    provider = cfg.llm_openai
    return OpenAILLM(provider.api_key, provider.base_url, provider.model, debug=cfg.debug_llm_logging)


def get_vector_store(cfg: WorkerConfig) -> BaseVectorStore:
    if cfg.vector_store == "local":
        return SimpleVectorStore(cfg.vector_store_path)
    return ChromaStore(cfg.vector_store_path)
