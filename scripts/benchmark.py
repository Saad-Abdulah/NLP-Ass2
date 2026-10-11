#!/usr/bin/env python3
"""Measure RAG latency, time-to-first-token (TTFT), and approximate tokens/sec via Ollama."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.conversation.orchestration import build_inference_context  # noqa: E402
from backend.app.domain.library import build_system_prompt  # noqa: E402
from backend.app.rag.retriever import LibraryRetriever  # noqa: E402


async def run() -> None:
    query = "Do you have Jurafsky's speech processing book and what is the loan period?"
    print(f"Query: {query}\n")

    # 1. Measure RAG latency
    retriever = LibraryRetriever()
    
    # Warm-up to load model into memory
    await retriever.retrieve("library catalogue warmup")

    # Run warm query (Cache Miss)
    t0 = time.perf_counter()
    rag_result_1 = await retriever.retrieve(query)
    t1 = time.perf_counter()
    rag_latency_ms = (t1 - t0) * 1000

    # Run again to measure cache hit
    t2 = time.perf_counter()
    rag_result_2 = await retriever.retrieve(query)
    t3 = time.perf_counter()
    cache_hit_ms = (t3 - t2) * 1000

    print(f"RAG Retrieval (Warm, Cache Miss): {rag_latency_ms:.1f} ms")
    print(f"RAG Retrieval (Cache Hit):        {cache_hit_ms:.2f} ms")
    print(f"RAG Confidence:                   {rag_result_1.confidence}")
    print(f"Chunks Retrieved:                 {len(rag_result_1.chunks)}\n")

    # 2. Build Inference Context
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": query},
    ]

    payload = build_inference_context(
        messages=messages,
        latest_user_text=query,
        retrieved_chunks=rag_result_1.chunks if rag_result_1.confidence != "none" else None,
        confidence=rag_result_1.confidence,
    )

    # 3. Stream from Ollama and measure TTFT + Generation
    base = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model
    url = f"{base}/api/chat"
    body = {"model": model, "messages": payload, "stream": True}

    first_token_at: float | None = None
    started = time.perf_counter()
    token_count = 0

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body) as response:
                if response.status_code != 200:
                    data = await response.aread()
                    print(f"Error: HTTP {response.status_code}\n{data.decode(errors='replace')}")
                    sys.exit(1)
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("done"):
                        break
                    chunk = (data.get("message") or {}).get("content") or ""
                    if chunk:
                        token_count += 1
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
    except Exception as exc:
        print(f"Ollama connection error: {exc}")
        sys.exit(1)

    ended = time.perf_counter()
    ttft_ms = ((first_token_at - started) * 1000) if first_token_at else 0.0
    total = ended - started
    gen_time = (ended - first_token_at) if first_token_at else 0.0
    tps = (token_count / gen_time) if gen_time > 0 else 0.0

    print(f"Model: {model}")
    print(f"Time to First Token: {ttft_ms:.1f} ms")
    print(f"Total Generation Time: {gen_time:.3f} s")
    print(f"Stream chunks (proxy for tokens): {token_count}")
    print(f"Approx generation speed: {tps:.1f} chunks/s")


if __name__ == "__main__":
    if os.getenv("PYTHONPATH") is None:
        os.environ["PYTHONPATH"] = str(ROOT)
    asyncio.run(run())
