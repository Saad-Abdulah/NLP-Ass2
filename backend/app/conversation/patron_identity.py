"""
Patron name/identity utilities — stripped to card-number lookup only.

Name recall is now handled inside ConversationManager via SessionState.facts,
which the LLM sees through per-turn context injection.  The old short-circuit
that fired before the LLM ever saw session history has been removed (P4/P8 fix).
"""

import re

from backend.app.domain.library import DEMO_PATRON

_CARD_PATTERN = re.compile(re.escape(DEMO_PATRON["card_number"]), re.I)


def patron_card_cited(user_text: str) -> bool:
    """True if the user's message contains the demo patron card number."""
    return bool(_CARD_PATTERN.search(user_text))


def card_account_reply() -> str:
    """
    Deterministic reply for direct card-number account queries.
    Only used when the patron explicitly cites P-78421 and asks about the account.
    """
    return (
        f"The library account for card {DEMO_PATRON['card_number']} is registered to "
        f"{DEMO_PATRON['name']}. I am the NUCES Virtual Desk — I do not share that "
        f"patron's name as my own. "
        f"Need help with loans or catalogue items on that card?"
    )
