"""Domain types for headroom-cli."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PruneAction:
    """A single pruning action to apply to a session part."""

    part_id: str
    message_id: str
    action: str  # "remove" | "replace" | "truncate"
    reason: str
    original_bytes: int
    pruned_bytes: int
    replacement: dict[str, object] | None = None


@dataclass
class StrategyResult:
    """Result of running one strategy against a session."""

    name: str
    actions: list[PruneAction] = field(default_factory=list)
    bytes_saved: int = 0
    parts_affected: int = 0


@dataclass
class PrescriptionResult:
    """Result of running a full prescription (ordered strategies)."""

    prescription: str
    strategies: list[StrategyResult] = field(default_factory=list)
    total_bytes_saved: int = 0
    total_parts_affected: int = 0


@dataclass
class StrategyInfo:
    """Metadata about a registered strategy."""

    name: str
    description: str
    tier: str
    expected_savings: str
    func: object  # callable


# --- Generic message format (client-agnostic) ---


@dataclass
class PartInfo:
    """A message part (generic format)."""

    id: str
    type: str  # "text" | "tool_call" | "tool_result" | etc.
    content: str | None = None
    tool: str | None = None
    input_data: dict[str, object] | None = None
    output_data: str | None = None
    size_bytes: int = 0


@dataclass
class MessageInfo:
    """A message (generic format)."""

    id: str
    role: str  # "user" | "assistant" | "system"
    timestamp: int
    parts: list[PartInfo] = field(default_factory=list)


# --- OpenCode-specific data shapes (for adapter) ---


@dataclass
class OpenCodeSessionInfo:
    """An OpenCode session record."""

    id: str
    title: str
    directory: str
    cost: float
    tokens_input: int
    tokens_output: int
    time_created: int
    time_updated: int


@dataclass
class OpenCodeMessageInfo:
    """An OpenCode message record."""

    id: str
    session_id: str
    role: str
    time_created: int
    data: dict[str, object]


@dataclass
class OpenCodePartInfo:
    """An OpenCode message-part record."""

    id: str
    message_id: str
    session_id: str
    part_type: str
    time_created: int
    data: dict[str, object]
    byte_size: int
