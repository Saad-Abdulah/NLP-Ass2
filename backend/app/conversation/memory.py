"""
Session state and memory management.

Key upgrades over Ass 1:
- Token-aware trimming (rough_token_count) instead of message-count trimming.
- SessionState carries `facts` dict for in-session user identity recall.
- SessionState carries `last_refusal_idx` to rotate varied refusal strings.
"""

import time
from dataclasses import dataclass, field
from typing import Literal


Role = Literal["system", "user", "assistant", "summary"]


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class SessionState:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    last_access: float = field(default_factory=time.time)

    # In-session user facts (name, card number, etc.) extracted from chat.
    facts: dict[str, str] = field(default_factory=dict)

    # Tracks which refusal string was last used (for rotation).
    last_refusal_idx: int = field(default=-1)

    # Tracks whether RAG was used in the last turn (for context_usage frame).
    last_rag_used: bool = field(default=False)

    def touch(self) -> None:
        self.last_access = time.time()


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def rough_token_count(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 characters (standard heuristic)."""
    return max(1, len(text) // 4)


def session_tokens_used(messages: list[Message]) -> int:
    """Total rough-token count of all messages in the session."""
    return sum(rough_token_count(m.content) for m in messages)


# ---------------------------------------------------------------------------
# History trimming
# ---------------------------------------------------------------------------

def trim_history_by_tokens(
    messages: list[Message],
    max_tokens: int,
) -> list[Message]:
    """
    Keep the system/summary message(s) and as many recent dialogue turns as
    fit within `max_tokens`.  Oldest non-system turns are dropped first.

    A 'summary' message (compressed history) is treated like the system prompt
    and is always preserved.
    """
    if not messages:
        return messages

    # Partition: anchors (system + summary) are always kept.
    anchors = [m for m in messages if m.role in ("system", "summary")]
    dialogue = [m for m in messages if m.role not in ("system", "summary")]

    anchor_tokens = sum(rough_token_count(m.content) for m in anchors)
    budget = max_tokens - anchor_tokens

    if budget <= 0:
        # System prompt alone exceeds budget — keep only system.
        return anchors

    # Walk newest-first and collect turns that fit.
    kept: list[Message] = []
    used = 0
    for msg in reversed(dialogue):
        t = rough_token_count(msg.content)
        if used + t > budget:
            break
        kept.append(msg)
        used += t

    kept.reverse()
    return anchors + kept
