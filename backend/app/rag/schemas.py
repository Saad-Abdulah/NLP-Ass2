"""RAG data schemas."""

from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    """A single retrieved document chunk from the vector store."""
    content: str
    doc_id: str
    category: str       # e.g. "book_catalogue", "policy", "faq"
    similarity: float   # cosine similarity 0.0–1.0
    source_file: str    # relative path inside data/documents/
    title: str          # human-readable document title for citations


@dataclass
class RetrievalResult:
    """
    Full result from a retrieval call, including confidence classification.
    """
    chunks: list[RetrievedChunk] = field(default_factory=list)
    confidence: str = "none"   # "high" | "medium_strong" | "medium" | "low" | "none"
    cached: bool = False
    latency_ms: float = 0.0
