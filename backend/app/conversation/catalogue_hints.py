"""
Turn-level hints for patron account queries (prompt-based, not RAG).

Stripped to only what RAG cannot handle:
  - DEMO_PATRON loan/due-date lookup (single card P-78421, from system prompt)
  - Casual greeting detection (used to skip unnecessary RAG on pure greetings)

Title/alias matching removed — RAG replaces it.
Policy question routing removed — RAG replaces it.
"""

import re

from backend.app.domain.library import DEMO_PATRON

_PATRON_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(re.escape(DEMO_PATRON["card_number"]), re.I),
    re.compile(r"\bdue (?:this week|today|tomorrow|soon)\b", re.I),
    re.compile(r"\bmy (?:loan|book|due date)\b", re.I),
)

_GREETING_WORDS = r"(?:hi|hello|hey|hi there|hello there|good\s+morning|good\s+afternoon|good\s+evening|good\s+day|assalam\w*|salam\w*|greetings)"
_GREETING_PATTERN = re.compile(
    rf"^[\s,!.]*(?:{_GREETING_WORDS}[\s,!.]*)+$",
    re.I,
)


def is_patron_query(user_text: str) -> bool:
    """True if the message is asking about patron P-78421's loans/due dates."""
    return any(p.search(user_text) for p in _PATRON_QUERY_PATTERNS)


def is_casual_greeting(user_text: str) -> bool:
    """
    True only when the ENTIRE message is a greeting with no other content.
    A combined message like 'Hi, do you have Clean Code?' returns False so RAG
    still runs and the catalogue question gets answered.
    """
    return bool(_GREETING_PATTERN.fullmatch(user_text.strip()))


def build_patron_hint(user_text: str, loans: list[dict] = None) -> str | None:
    """
    Returns a one-turn orchestration note for patron P-78421 loan queries.
    Returns None if not applicable.
    """
    if not is_patron_query(user_text):
        return None

    if loans is None:
        loans = DEMO_PATRON["loans"]

    loan_lines = []
    for loan in loans:
        used = loan.get("renewals_used", 0)
        remaining = max(0, 2 - used)
        loan_lines.append(
            f"- {loan['item_id']} \"{loan['title']}\" due {loan['due_date']} "
            f"(Renewals used: {used}/2; Renewals remaining: {remaining} left out of 2 max)"
        )
    return (
        f"[Patron account live records for this turn: Card {DEMO_PATRON['card_number']}:\n"
        + "\n".join(loan_lines)
        + "\nUse these exact due dates and renewal counts. State both renewals used and renewals remaining clearly.]"
    )
