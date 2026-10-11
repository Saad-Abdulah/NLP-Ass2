"""
Dynamic JSON database for Library Records (Catalogue & Patrons).
Provides thread-safe / async-safe operations for issuing, renewing,
and returning books, with persistent writes to data/library_records.json.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RECORDS_PATH = Path("data/library_records.json")

# Initial seed data if file does not exist
INITIAL_CATALOGUE = [
    {
        "id": "BK-1001",
        "title": "Introduction to Algorithms",
        "author": "Cormen, Leiserson, Rivest, Stein",
        "location": "Stacks A / QA76.9.A43",
        "status": "available",
        "due_date": None,
        "borrowed_by": None,
        "category": "computer_science",
    },
    {
        "id": "BK-1002",
        "title": "Speech and Language Processing",
        "author": "Daniel Jurafsky, James H. Martin",
        "location": "Stacks B / P98",
        "status": "available",
        "due_date": None,
        "borrowed_by": None,
        "category": "nlp_ai",
    },
    {
        "id": "BK-1003",
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "location": "Fiction / FIC FIT",
        "status": "checked_out",
        "due_date": "2026-09-22",
        "borrowed_by": "P-78421",
        "category": "fiction",
    },
    {
        "id": "BK-1004",
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "location": "Stacks A / QA76.73",
        "status": "available",
        "due_date": None,
        "borrowed_by": None,
        "category": "software_engineering",
    },
    {
        "id": "BK-1005",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "location": "Fiction / FIC AUS",
        "status": "on_hold",
        "due_date": None,
        "borrowed_by": None,
        "category": "fiction",
    },
    {
        "id": "BK-1006",
        "title": "Deep Learning",
        "author": "Goodfellow, Bengio, Courville",
        "location": "Reference (library use only)",
        "status": "reference_only",
        "due_date": None,
        "borrowed_by": None,
        "category": "ai_ml",
    },
    {
        "id": "BK-1010",
        "title": "Database System Concepts",
        "author": "Silberschatz, Korth, Sudarshan",
        "location": "Stacks A / QA76.9.D3",
        "status": "checked_out",
        "due_date": "2026-09-18",
        "borrowed_by": "P-78421",
        "category": "databases",
    },
    {
        "id": "BK-1011",
        "title": "Design Patterns",
        "author": "Gamma, Helm, Johnson, Vlissides",
        "location": "Stacks A / QA76.76.D47",
        "status": "available",
        "due_date": None,
        "borrowed_by": None,
        "category": "software_engineering",
    },
    {
        "id": "BK-1018",
        "title": "Pattern Recognition and Machine Learning",
        "author": "Christopher M. Bishop",
        "location": "Stacks B / Q325.5",
        "status": "available",
        "due_date": None,
        "borrowed_by": None,
        "category": "ai_ml",
    },
    {
        "id": "BK-1021",
        "title": "The Pragmatic Programmer",
        "author": "David Thomas, Andrew Hunt",
        "location": "Stacks A / QA76.6",
        "status": "available",
        "due_date": None,
        "borrowed_by": None,
        "category": "software_engineering",
    },
]

INITIAL_PATRONS = {
    "P-78421": {
        "card_number": "P-78421",
        "name": "Alex Rivera",
        "email": "alex.rivera@nu.edu.pk",
        "status": "active",
        "loans": [
            {
                "item_id": "BK-1003",
                "title": "The Great Gatsby",
                "due_date": "2026-10-18",
                "renewals_used": 0,
            },
            {
                "item_id": "BK-1010",
                "title": "Database System Concepts",
                "due_date": "2026-10-15",
                "renewals_used": 1,
            },
        ],
    }
}


class RecordsDatabase:
    """Thread-safe persistent JSON database manager."""

    def __init__(self, filepath: Path = RECORDS_PATH) -> None:
        self.filepath = filepath
        self._lock = asyncio.Lock()
        self._init_file()

    def reset_database(self) -> None:
        """Reset the JSON database to pristine initial state."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "catalogue": INITIAL_CATALOGUE,
            "patrons": INITIAL_PATRONS,
            "metadata": {
                "updated_at": datetime.now().isoformat(),
                "total_books": len(INITIAL_CATALOGUE),
            },
        }
        self._save_raw(data)
        logger.info("Reset dynamic records database at %s", self.filepath)

    def _init_file(self) -> None:
        """Create initial database file if not present."""
        if not self.filepath.exists():
            self.reset_database()

    def _read_raw(self) -> dict[str, Any]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to read records JSON: %s. Re-initializing.", exc)
            self._init_file()
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)

    def _save_raw(self, data: dict[str, Any]) -> None:
        data.setdefault("metadata", {})["updated_at"] = datetime.now().isoformat()
        # Atomic write via temp file
        temp_path = self.filepath.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, self.filepath)

    async def get_catalogue(self) -> list[dict[str, Any]]:
        async with self._lock:
            data = self._read_raw()
            return data.get("catalogue", [])

    async def get_patron(self, card_number: str) -> dict[str, Any] | None:
        async with self._lock:
            data = self._read_raw()
            patrons = data.get("patrons", {})
            return patrons.get(card_number.upper().strip())

    async def search_books(self, query: str) -> list[dict[str, Any]]:
        q = query.lower().strip()
        async with self._lock:
            data = self._read_raw()
            matches = []
            for b in data.get("catalogue", []):
                if (
                    q in b.get("id", "").lower()
                    or q in b.get("title", "").lower()
                    or q in b.get("author", "").lower()
                ):
                    matches.append(b)
            return matches

    async def find_book(self, identifier: str) -> dict[str, Any] | None:
        ident = identifier.lower().strip()
        async with self._lock:
            data = self._read_raw()
            for b in data.get("catalogue", []):
                if b.get("id", "").lower() == ident:
                    return b
                if ident in b.get("title", "").lower():
                    return b
            return None

    async def issue_book(
        self, card_number: str, identifier: str
    ) -> dict[str, Any]:
        """
        Issue / borrow a book for a patron.
        Updates status to 'checked_out', calculates due date (21 days),
        adds loan to patron's records, and saves to JSON file.
        """
        card = card_number.upper().strip()
        ident = identifier.lower().strip()

        async with self._lock:
            data = self._read_raw()
            catalogue = data.setdefault("catalogue", [])
            patrons = data.setdefault("patrons", {})

            # 1. Verify patron exists, or register if standard patron
            if card not in patrons:
                patrons[card] = {
                    "card_number": card,
                    "name": f"Patron ({card})",
                    "status": "active",
                    "loans": [],
                }

            patron = patrons[card]
            active_loans = patron.setdefault("loans", [])

            # Check borrowing policy: Max active loans is 10
            if len(active_loans) >= 10:
                return {
                    "success": False,
                    "error": f"Borrowing limit reached: Card {card} already has 10 active loans.",
                }

            # 2. Find book in catalogue
            book = None
            for b in catalogue:
                if b.get("id", "").lower() == ident or ident in b.get("title", "").lower():
                    book = b
                    break

            if not book:
                return {
                    "success": False,
                    "error": f"Book matching '{identifier}' not found in catalogue.",
                }

            # Check status
            if book.get("status") == "checked_out":
                due = book.get("due_date", "unknown")
                return {
                    "success": False,
                    "error": f"'{book['title']}' ({book['id']}) is already checked out (due {due}). You may place a hold.",
                }
            if book.get("status") == "reference_only":
                return {
                    "success": False,
                    "error": f"'{book['title']}' ({book['id']}) is a Reference item and does not circulate.",
                }
            if book.get("status") == "on_hold":
                return {
                    "success": False,
                    "error": f"'{book['title']}' ({book['id']}) is currently on hold for another patron.",
                }

            # 3. Issue book: 21 days loan
            due_date = (date.today() + timedelta(days=21)).isoformat()
            book["status"] = "checked_out"
            book["due_date"] = due_date
            book["borrowed_by"] = card

            new_loan = {
                "item_id": book["id"],
                "title": book["title"],
                "due_date": due_date,
                "renewals_used": 0,
            }
            active_loans.append(new_loan)

            self._save_raw(data)
            logger.info("Issued %s to %s, due %s", book["id"], card, due_date)

            return {
                "success": True,
                "book_id": book["id"],
                "title": book["title"],
                "card_number": card,
                "due_date": due_date,
                "message": f"Successfully issued '{book['title']}' ({book['id']}) to card {card}. Due date is {due_date} (21-day loan).",
            }

    async def renew_book(
        self, card_number: str, identifier: str
    ) -> dict[str, Any]:
        """
        Renew an active loan for a patron.
        Checks policy (max 2 renewals, not on hold), updates due date (+21 days),
        increments renewals_used, and saves to JSON file.
        """
        card = card_number.upper().strip()
        ident = identifier.lower().strip()

        async with self._lock:
            data = self._read_raw()
            catalogue = data.setdefault("catalogue", [])
            patrons = data.setdefault("patrons", {})

            if card not in patrons:
                return {
                    "success": False,
                    "error": f"No account found for card number {card}.",
                }

            patron = patrons[card]
            loans = patron.get("loans", [])

            loan = None
            for l in loans:
                if l.get("item_id", "").lower() == ident or ident in l.get("title", "").lower():
                    loan = l
                    break

            if not loan:
                return {
                    "success": False,
                    "error": f"No active loan for '{identifier}' found under card {card}.",
                }

            # Check renewals policy
            renewals_used = loan.get("renewals_used", 0)
            if renewals_used >= 2:
                return {
                    "success": False,
                    "error": f"Renewal limit reached: '{loan['title']}' has already been renewed 2 times.",
                }

            # Calculate new due date (21 days from current due date or today)
            curr_due_str = loan.get("due_date")
            try:
                base_date = datetime.strptime(curr_due_str, "%Y-%m-%d").date()
                if base_date < date.today():
                    base_date = date.today()
            except Exception:
                base_date = date.today()

            new_due = (base_date + timedelta(days=21)).isoformat()
            loan["due_date"] = new_due
            loan["renewals_used"] = renewals_used + 1

            # Update catalogue entry as well
            for b in catalogue:
                if b.get("id") == loan.get("item_id"):
                    b["due_date"] = new_due
                    break

            self._save_raw(data)
            logger.info("Renewed %s for %s, new due date %s", loan['item_id'], card, new_due)

            return {
                "success": True,
                "book_id": loan["item_id"],
                "title": loan["title"],
                "card_number": card,
                "due_date": new_due,
                "renewals_used": loan["renewals_used"],
                "message": f"Successfully renewed '{loan['title']}' ({loan['item_id']}) on card {card}. New due date is {new_due}. Renewals used: {loan['renewals_used']}/2.",
            }

    async def return_book(
        self, card_number: str, identifier: str
    ) -> dict[str, Any]:
        """
        Return a checked-out book.
        Sets status to 'available', clears due_date and borrowed_by,
        removes from patron loans, and saves to JSON file.
        """
        card = card_number.upper().strip()
        ident = identifier.lower().strip()

        async with self._lock:
            data = self._read_raw()
            catalogue = data.setdefault("catalogue", [])
            patrons = data.setdefault("patrons", {})

            # Find in catalogue
            book = None
            for b in catalogue:
                if b.get("id", "").lower() == ident or ident in b.get("title", "").lower():
                    book = b
                    break

            if not book:
                return {
                    "success": False,
                    "error": f"Book matching '{identifier}' not found in catalogue.",
                }

            book["status"] = "available"
            book["due_date"] = None
            book["borrowed_by"] = None

            # Remove from patron loans if present
            if card in patrons:
                loans = patrons[card].get("loans", [])
                patrons[card]["loans"] = [
                    l for l in loans if l.get("item_id") != book["id"]
                ]

            self._save_raw(data)
            logger.info("Returned %s from %s", book['id'], card)

            return {
                "success": True,
                "book_id": book["id"],
                "title": book["title"],
                "message": f"'{book['title']}' ({book['id']}) has been marked as returned and is now available in the catalogue.",
            }

    async def check_patron_loans(self, card_number: str) -> dict[str, Any]:
        card = card_number.upper().strip()
        async with self._lock:
            data = self._read_raw()
            patrons = data.get("patrons", {})
            if card not in patrons:
                return {
                    "success": False,
                    "card_number": card,
                    "loans": [],
                    "message": f"No active account found for card {card}.",
                }
            patron = patrons[card]
            return {
                "success": True,
                "card_number": card,
                "name": patron.get("name", "Patron"),
                "loans": patron.get("loans", []),
            }


# Global singleton instance
records_db = RecordsDatabase()
