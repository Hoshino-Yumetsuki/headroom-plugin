"""Token estimation utilities — stdlib only, no tokenizer deps."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from headroom_cli._constants import CHARS_PER_TOKEN, DEFAULT_CONTEXT_WINDOW

if TYPE_CHECKING:
    from headroom_cli.types import MessageInfo, PartInfo, SessionInfo


def estimate_tokens(text: str) -> int:
    """Estimate token count using len/4 heuristic."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_part_tokens(part: PartInfo) -> int:
    """Estimate tokens for a single part based on its serialized data."""
    raw = json.dumps(part.data, separators=(",", ":"), default=str)
    return estimate_tokens(raw)


def estimate_session_tokens(
    messages: list[MessageInfo],
    parts: list[PartInfo],
) -> int:
    """Estimate total token count for a session."""
    total = 0
    for msg in messages:
        # Role + structural overhead ~ 4 tokens per message
        total += 4
    for part in parts:
        total += estimate_part_tokens(part)
    return total


def detect_context_window(session: SessionInfo) -> int:
    """Detect context window from session metadata."""
    # OpenCode stores model info in the session; try to infer from title/dir
    # Fallback to default
    title_lower = session.title.lower() if session.title else ""
    # Common model context sizes
    if "gpt-4o" in title_lower or "gpt-4-turbo" in title_lower:
        return 128_000
    if "claude" in title_lower:
        return 200_000
    if "gemini" in title_lower:
        return 1_000_000
    return DEFAULT_CONTEXT_WINDOW
