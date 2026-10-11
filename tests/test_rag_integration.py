import pytest
from backend.app.rag.retriever import LibraryRetriever

@pytest.mark.asyncio
async def test_retrieves_relevant_chunk():
    retriever = LibraryRetriever()
    
    # Run retrieval
    result = await retriever.retrieve("Jurafsky speech processing")
    
    # We expect a high/med confidence match with chunks
    assert result.confidence in ["high", "medium"]
    assert len(result.chunks) > 0
    
    # Verify the chunk contains something related to the book
    content = result.chunks[0].content.lower()
    assert "jurafsky" in content or "speech" in content
