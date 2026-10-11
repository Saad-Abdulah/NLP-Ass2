import json
import pytest
from backend.app.domain.records import records_db
from backend.app.domain.tools import execute_tool


@pytest.mark.asyncio
async def test_records_db_issue_and_return():
    card = "P-99999"
    book_id = "BK-1004"  # Clean Code

    # Ensure book is returned initially if left from previous runs
    await records_db.return_book(card_number=card, identifier=book_id)

    # 1. Issue book
    issue_res = await records_db.issue_book(card_number=card, identifier=book_id)
    assert issue_res["success"] is True
    assert "Successfully issued" in issue_res["message"]
    assert issue_res["book_id"] == "BK-1004"

    # Verify JSON file has updated status
    book = await records_db.find_book(book_id)
    assert book["status"] == "checked_out"
    assert book["borrowed_by"] == card

    # 2. Try to issue again (should fail because it's already checked out)
    issue_again = await records_db.issue_book(card_number="P-11111", identifier=book_id)
    assert issue_again["success"] is False
    assert "already checked out" in issue_again["error"]

    # 3. Return book
    return_res = await records_db.return_book(card_number=card, identifier=book_id)
    assert return_res["success"] is True
    book_after = await records_db.find_book(book_id)
    assert book_after["status"] == "available"
    assert book_after["borrowed_by"] is None


@pytest.mark.asyncio
async def test_tool_calling_renew():
    card = "P-78421"
    book_title = "The Great Gatsby"

    # Reset renewals_used to 0 in database so test is idempotent
    data = records_db._read_raw()
    for l in data.get("patrons", {}).get(card, {}).get("loans", []):
        if l.get("item_id") == "BK-1003":
            l["renewals_used"] = 0
    records_db._save_raw(data)

    # Execute renew tool
    res = await execute_tool("renew_book", {"card_number": card, "book_title_or_id": book_title})
    assert res["success"] is True
    assert "Successfully renewed" in res["message"]
    assert res["card_number"] == card
    assert "due_date" in res

    # Verify patron records
    patron = await records_db.get_patron(card)
    assert patron is not None
    loans = patron["loans"]
    gatsby_loan = next((l for l in loans if l["item_id"] == "BK-1003"), None)
    assert gatsby_loan is not None
    assert gatsby_loan["renewals_used"] == 1


def test_websocket_tool_calling_renewal():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    import uuid

    # Reset renewals_used to 0 so renewal is allowed
    data = records_db._read_raw()
    for l in data.get("patrons", {}).get("P-78421", {}).get("loans", []):
        if l.get("item_id") == "BK-1003":
            l["renewals_used"] = 0
    records_db._save_raw(data)

    client = TestClient(app)
    session_id = str(uuid.uuid4())
    parts = []
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({
            "type": "user_message",
            "session_id": session_id,
            "content": "Please renew The Great Gatsby on my card P-78421."
        }))
        while True:
            frame = json.loads(ws.receive_text())
            if frame["type"] == "token":
                parts.append(frame.get("content", ""))
            elif frame["type"] == "done":
                break
            elif frame["type"] == "error":
                raise AssertionError(frame.get("message"))
    reply = "".join(parts).lower()
    assert "gatsby" in reply or "renew" in reply or "due" in reply
