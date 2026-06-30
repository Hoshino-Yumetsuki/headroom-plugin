"""Strategy-specific configuration constants."""
from __future__ import annotations

# Gentle
COMPACTION_MARKER_TEXT = "compaction"

# Standard
ERROR_TURN_AGE = 5  # Drop errored tool inputs after N turns
REASONING_KEEP_CHARS = 200  # Keep first N chars of reasoning blocks

# Aggressive
LARGE_OUTPUT_THRESHOLD = 8192  # Bytes — truncate tool outputs above this
LARGE_OUTPUT_KEEP_CHARS = 500  # Keep first N chars after truncation
OLD_CONTEXT_DEFAULT_K = 20  # Drop messages beyond last K turns
THINNING_KEEP_RATIO = 0.5  # Keep every Nth assistant message in old turns
