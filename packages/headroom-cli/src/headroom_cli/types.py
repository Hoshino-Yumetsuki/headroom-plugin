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


# --- OpenCode data shapes ---


@dataclass
class SessionInfo:
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
class MessageInfo:
    """An OpenCode message record."""

    id: str
    session_id: str
    role: str
    time_created: int
    data: dict[str, object]


@dataclass
class PartInfo:
    """An OpenCode message-part record."""

    id: str
    message_id: str
    session_id: str
    part_type: str
    time_created: int
    data: dict[str, object]
    byte_size: int
