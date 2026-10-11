"""
LLM Tool Calling (Function Calling) definitions and dispatcher for OPAC Library Assistant.
Conforms to OpenAI / Ollama standard tool calling specification.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from backend.app.domain.records import records_db

logger = logging.getLogger(__name__)

# Standard JSON schema specifications for Ollama tool calling
LIBRARY_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "renew_book",
            "description": "Renew an active book loan for a library patron card (e.g. card P-78421). Updates the record and grants a 21-day extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_number": {
                        "type": "string",
                        "description": "The patron's library card number, e.g. 'P-78421'.",
                    },
                    "book_title_or_id": {
                        "type": "string",
                        "description": "The book title or item ID to renew (e.g. 'The Great Gatsby' or 'BK-1003').",
                    },
                },
                "required": ["card_number", "book_title_or_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_book",
            "description": "Issue or borrow a book from the library catalogue for a patron card (e.g. card P-78421). Checks availability and borrowing limit (max 10 active loans) and updates the record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_number": {
                        "type": "string",
                        "description": "The patron's library card number, e.g. 'P-78421'.",
                    },
                    "book_title_or_id": {
                        "type": "string",
                        "description": "The book title or item ID to issue/checkout (e.g. 'Clean Code' or 'BK-1004').",
                    },
                },
                "required": ["card_number", "book_title_or_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "return_book",
            "description": "Return an issued book back to the library collection, marking it available again.",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_number": {
                        "type": "string",
                        "description": "The patron's library card number, e.g. 'P-78421'.",
                    },
                    "book_title_or_id": {
                        "type": "string",
                        "description": "The title or ID of the book being returned.",
                    },
                },
                "required": ["card_number", "book_title_or_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_patron_loans",
            "description": "Look up active loans, due dates, and remaining renewals for a library patron card.",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_number": {
                        "type": "string",
                        "description": "The patron's library card number, e.g. 'P-78421'.",
                    },
                },
                "required": ["card_number"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    """
    Execute a requested tool call against the persistent records database.
    Handles JSON argument parsing and validation.
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            arguments = {}

    card_number = str(arguments.get("card_number") or "").strip()
    book_ident = str(
        arguments.get("book_title_or_id")
        or arguments.get("identifier")
        or arguments.get("title")
        or arguments.get("book_id")
        or ""
    ).strip()

    logger.info("Executing tool: %s with args: card=%s, book=%s", name, card_number, book_ident)

    if name == "renew_book":
        if not card_number or not book_ident:
            return {"success": False, "error": "Missing card_number or book_title_or_id"}
        return await records_db.renew_book(card_number=card_number, identifier=book_ident)

    elif name == "issue_book":
        if not card_number or not book_ident:
            return {"success": False, "error": "Missing card_number or book_title_or_id"}
        return await records_db.issue_book(card_number=card_number, identifier=book_ident)

    elif name == "return_book":
        if not card_number or not book_ident:
            return {"success": False, "error": "Missing card_number or book_title_or_id"}
        return await records_db.return_book(card_number=card_number, identifier=book_ident)

    elif name == "check_patron_loans":
        if not card_number:
            return {"success": False, "error": "Missing card_number"}
        return await records_db.check_patron_loans(card_number=card_number)

    else:
        return {"success": False, "error": f"Unknown tool: '{name}'"}
