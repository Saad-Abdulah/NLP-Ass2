import json

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "model" in data


def test_library_info_endpoint() -> None:
    response = client.get("/api/library-info")
    assert response.status_code == 200
    data = response.json()
    assert data["library_name"] == "OPAC FAST NUCES"
    assert data["assistant_name"] == "NUCES Virtual Desk"
    assert data["sample_patron_card"] == "P-78421"
    assert "virtual_desk_availability" in data


def test_websocket_invalid_json_returns_error() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text("not-json")
        raw = ws.receive_text()
        payload = json.loads(raw)
        assert payload["type"] == "error"


def test_websocket_empty_session_id_rejected() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "user_message", "session_id": "", "content": "hi"}))
        raw = ws.receive_text()
        payload = json.loads(raw)
        assert payload["type"] == "error"


def test_websocket_whitespace_only_rejected() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "user_message", "session_id": "abc", "content": "   "}))
        raw = ws.receive_text()
        payload = json.loads(raw)
        assert payload["type"] == "error"


def test_websocket_unknown_type_rejected() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "ping", "session_id": "abc"}))
        raw = ws.receive_text()
        payload = json.loads(raw)
        assert payload["type"] == "error"


def test_websocket_reset_ack() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"type": "reset_session", "session_id": "session-1"}))
        raw = ws.receive_text()
        payload = json.loads(raw)
        assert payload["type"] == "session_reset"
        assert payload["session_id"] == "session-1"


def test_index_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "OPAC FAST NUCES" in response.text


def test_help_page_served() -> None:
    response = client.get("/help.html")
    assert response.status_code == 200
    assert "Patron card P-78421" in response.text


def test_websocket_my_name_not_assistant_identity() -> None:
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "user_message",
                    "session_id": "name-test-session",
                    "content": "tell me my name plz",
                }
            )
        )
        parts: list[str] = []
        while True:
            payload = json.loads(ws.receive_text())
            if payload["type"] == "token":
                parts.append(payload.get("content", ""))
            elif payload["type"] == "done":
                break
            elif payload["type"] == "error":
                raise AssertionError(payload.get("message"))
        reply = "".join(parts).lower()
        assert "my name is alex" not in reply
        assert "i am alex" not in reply


def _ws_collect_reply(ws, payload: dict) -> str:
    ws.send_text(json.dumps(payload))
    parts: list[str] = []
    while True:
        frame = json.loads(ws.receive_text())
        if frame["type"] == "token":
            parts.append(frame.get("content", ""))
        elif frame["type"] == "done":
            return "".join(parts)
        if frame["type"] == "error":
            raise AssertionError(frame.get("message"))


def test_websocket_multi_turn_gates_same_session() -> None:
    session_id = "multi-turn-gates"
    with client.websocket_connect("/ws/chat") as ws:
        joke = _ws_collect_reply(
            ws,
            {
                "type": "user_message",
                "session_id": session_id,
                "content": "tell me a joke plz",
            },
        ).lower()
        assert "library" in joke or "catalogue" in joke or "cannot" in joke

        name = _ws_collect_reply(
            ws,
            {
                "type": "user_message",
                "session_id": session_id,
                "content": "tell me my name plz",
            },
        ).lower()
        assert "my name is alex" not in name
