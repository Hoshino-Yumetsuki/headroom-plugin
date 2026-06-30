"""Shared constants for headroom-cli."""
from __future__ import annotations

# Default context window sizes by model family
DEFAULT_CONTEXT_WINDOW = 200_000
SYSTEM_OVERHEAD_TOKENS = 4_000

# Token estimation
CHARS_PER_TOKEN = 4

# Safety thresholds
DEFAULT_MAX_DROP_PCT = 0.50
DEFAULT_PRESERVE_LAST_K = 10
DEFAULT_GUARD_THRESHOLD = 0.80
DEFAULT_GUARD_INTERVAL = 30

# Backup suffix
BACKUP_SUFFIX = ".headroom-backup"

# Part type categories for diagnosis
TOOL_OUTPUT_TYPES = frozenset({"tool-result", "tool_result"})
REASONING_TYPES = frozenset({"thinking", "reasoning"})
FILE_READ_TYPES = frozenset({"file-read", "file_read", "read-file"})
IMAGE_TYPES = frozenset({"image", "base64-image"})
METADATA_TYPES = frozenset({
    "step-start",
    "step-finish",
    "step_start",
    "step_finish",
    "retry-metadata",
    "retry_metadata",
})
