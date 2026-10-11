from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"
    request_timeout_seconds: float = 120.0

    # Session management
    max_server_sessions: int = 128

    # Context window (token-aware trimming)
    max_context_tokens: int = 3072   # rough-token budget for session history

    # RAG
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.30
    rag_max_chars: int = 2000        # max chars of injected RAG context per turn
    rag_chroma_dir: str = "data/chroma_db"
    rag_documents_dir: str = "data/documents"
    rag_collection: str = "library_v1"
    rag_cache_size: int = 256        # LRU cache entries for retrieval results

    # Summariser
    summarise_auto_threshold: float = 0.95  # trigger auto-summarise at 95% context

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
