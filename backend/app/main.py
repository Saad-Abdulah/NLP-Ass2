"""
FastAPI application entry point.

Changes for Assignment 2:
- Single OllamaEngine (P9 fix) — health check routes through ConversationManager.
- Input sanitiser before manager.stream_reply (G1).
- Per-connection rate limiter: max 10 messages / 60 s (G2).
- Handles new WebSocket message types: request_summarise.
- Emits RagSourcesFrame, ContextUsageFrame, SummariseAck over WebSocket.
- Structured logging to logs/app.log (G8).
"""

import json
import logging
import logging.handlers
import re
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend.app.config import settings
from backend.app.conversation.manager import ConversationManager
from backend.app.domain.library import LIBRARY_NAME, VIRTUAL_DESK_AVAILABILITY
from backend.app.domain.persona import (
    ASSISTANT_NAME,
    ASSISTANT_ROLE,
    GREETING,
    LIBRARY_TAGLINE,
    SAMPLE_PATRON_CARD,
)
from backend.app.models.schemas import (
    ChatDone,
    ChatError,
    ChatInbound,
    ChatRateLimit,
    ChatSessionReset,
    ChatSessionResetAck,
    ChatToken,
    ContextUsageFrame,
    HealthResponse,
    LibraryInfoResponse,
    RagSourcesFrame,
    SummariseAck,
    SummariseRequest,
)

# ---------------------------------------------------------------------------
# Logging setup (G8)
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # Keep console output too
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)-8s %(name)s  %(message)s"))
    root.addHandler(console)


_setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
MAX_WS_FRAME_CHARS = 16_000
RATE_LIMIT_MAX = 10     # messages
RATE_LIMIT_WINDOW = 60  # seconds

# ---------------------------------------------------------------------------
# Input sanitiser (G1)
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")


def sanitise_input(text: str) -> str:
    """Strip ANSI codes, collapse whitespace, reject obvious base64 blobs."""
    text = _ANSI_RE.sub("", text)
    if _BASE64_BLOB_RE.search(text):
        raise ValueError("Message contains encoded content and cannot be processed.")
    # Collapse runs of whitespace (except newlines which may be intentional)
    text = re.sub(r"[ \t]{3,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# App & manager
# ---------------------------------------------------------------------------

app = FastAPI(title="Library Assistant API", version="2.0.0")
manager = ConversationManager()


def _validation_message(exc: ValidationError) -> str:
    if exc.errors():
        return str(exc.errors()[0].get("msg", "Invalid request."))
    return "Invalid request."


async def _send_error(websocket: WebSocket, session_id: str, message: str) -> None:
    err = ChatError(session_id=session_id or "unknown", message=message)
    try:
        await websocket.send_text(err.model_dump_json())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ok = await manager.health_check()
    status = "ok" if ok else "degraded"
    return HealthResponse(status=status, model=settings.ollama_model)


@app.get("/api/library-info", response_model=LibraryInfoResponse)
async def library_info() -> LibraryInfoResponse:
    return LibraryInfoResponse(
        library_name=LIBRARY_NAME,
        virtual_desk_availability=VIRTUAL_DESK_AVAILABILITY,
        assistant_name=ASSISTANT_NAME,
        assistant_role=ASSISTANT_ROLE,
        tagline=LIBRARY_TAGLINE,
        greeting=GREETING,
        sample_patron_card=SAMPLE_PATRON_CARD,
        max_context_tokens=settings.max_context_tokens,
    )

@app.get("/api/sources")
async def list_sources() -> list[dict[str, str]]:
    docs_dir = ROOT / "data" / "documents"
    sources = []
    if docs_dir.is_dir():
        for md_file in sorted(docs_dir.glob("*.md")):
            sources.append({"doc_id": md_file.stem, "title": md_file.name})
    return sources

@app.get("/api/sources/{doc_id}")
async def get_source(doc_id: str) -> dict[str, str]:
    docs_dir = ROOT / "data" / "documents"
    md_file = docs_dir / f"{doc_id}.md"
    if not md_file.is_file():
        return {"error": "Source not found"}
    return {"doc_id": doc_id, "content": md_file.read_text(encoding="utf-8")}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = ""

    # Per-connection rate limit state
    message_timestamps: deque[float] = deque()

    def _rate_limited() -> bool:
        now = time.monotonic()
        while message_timestamps and now - message_timestamps[0] > RATE_LIMIT_WINDOW:
            message_timestamps.popleft()
        if len(message_timestamps) >= RATE_LIMIT_MAX:
            return True
        message_timestamps.append(now)
        return False

    try:
        while True:
            raw = await websocket.receive_text()

            if len(raw) > MAX_WS_FRAME_CHARS:
                await _send_error(websocket, session_id, "Message too large. Please shorten your request.")
                continue

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, session_id, "Invalid JSON payload.")
                continue

            if not isinstance(payload, dict):
                await _send_error(websocket, session_id, "Payload must be a JSON object.")
                continue

            msg_type = payload.get("type")

            # --- Reset session ---
            if msg_type == "reset_session":
                try:
                    reset = ChatSessionReset.model_validate(payload)
                except ValidationError as exc:
                    await _send_error(websocket, session_id, f"Invalid reset: {_validation_message(exc)}")
                    continue
                session_id = reset.session_id
                await manager.reset_session(session_id)
                ack = ChatSessionResetAck(session_id=session_id)
                await websocket.send_text(ack.model_dump_json())
                continue

            # --- Manual summarise ---
            if msg_type == "request_summarise":
                try:
                    req = SummariseRequest.model_validate(payload)
                except ValidationError as exc:
                    await _send_error(websocket, session_id, f"Invalid summarise request: {_validation_message(exc)}")
                    continue
                session_id = req.session_id
                try:
                    ack = await manager.summarise_session(session_id)
                    await websocket.send_text(ack.model_dump_json())
                except Exception as exc:
                    logger.exception("Summarisation error for session %s", session_id)
                    await _send_error(websocket, session_id, "Summarisation failed. Try again.")
                continue

            # --- User message ---
            if msg_type != "user_message":
                await _send_error(
                    websocket,
                    session_id,
                    "Unsupported message type. Use user_message, reset_session, or request_summarise.",
                )
                continue

            # Rate limit check
            if _rate_limited():
                rl = ChatRateLimit(session_id=session_id or "unknown")
                try:
                    await websocket.send_text(rl.model_dump_json())
                except Exception:
                    pass
                logger.warning("Rate limit hit for session %s", session_id)
                continue

            try:
                inbound = ChatInbound.model_validate(payload)
            except ValidationError as exc:
                await _send_error(websocket, session_id, f"Invalid message: {_validation_message(exc)}")
                continue

            session_id = inbound.session_id

            # Input sanitisation
            try:
                clean_content = sanitise_input(inbound.content)
            except ValueError as exc:
                await _send_error(websocket, session_id, str(exc))
                continue

            # Stream reply
            try:
                async for event_type, event_data in manager.stream_reply(session_id, clean_content):
                    if event_type == "token":
                        out = ChatToken(session_id=session_id, content=event_data["content"])
                        try:
                            await websocket.send_text(out.model_dump_json())
                        except WebSocketDisconnect:
                            return
                    elif event_type == "rag_sources":
                        try:
                            await websocket.send_text(event_data.model_dump_json())
                        except WebSocketDisconnect:
                            return
                    elif event_type == "context_usage":
                        try:
                            await websocket.send_text(event_data.model_dump_json())
                        except WebSocketDisconnect:
                            return

                done = ChatDone(session_id=session_id)
                await websocket.send_text(done.model_dump_json())

            except WebSocketDisconnect:
                return
            except RuntimeError as exc:
                await _send_error(websocket, session_id, str(exc))
            except Exception:
                logger.exception("Unexpected error during stream_reply for session %s", session_id)
                await _send_error(
                    websocket,
                    session_id,
                    "Model error. Check that Ollama is running and the configured model is pulled.",
                )

    except WebSocketDisconnect:
        return


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

if FRONTEND.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    @app.get("/help.html")
    async def help_page() -> FileResponse:
        return FileResponse(FRONTEND / "help.html")
