"""Public persona metadata for API and UI."""

from backend.app.domain.library import DEMO_PATRON, LIBRARY_NAME, VIRTUAL_DESK_AVAILABILITY

ASSISTANT_NAME = "NUCES Virtual Desk"
ASSISTANT_ROLE = "OPAC automated assistant"
LIBRARY_TAGLINE = "Virtual reference desk for catalogue, policy, and loans"
SAMPLE_PATRON_CARD = DEMO_PATRON["card_number"]

GREETING = (
    f"Welcome to {LIBRARY_NAME}. "
    f"I can help with catalogue search, borrowing rules, loan due dates, and renewals. "
    f"For account lookup, use patron card {SAMPLE_PATRON_CARD}. "
    "What would you like to look up?"
)
