"""Strategy registry and prescription definitions."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from headroom_cli.types import StrategyInfo

if TYPE_CHECKING:
    from headroom_cli.config import Config
    from headroom_cli.types import MessageInfo, PartInfo, StrategyResult

STRATEGIES: dict[str, StrategyInfo] = {}

PRESCRIPTIONS: dict[str, list[str]] = {
    "gentle": [
        "compaction-marker-collapse",
        "stale-file-read-strip",
        "base64-image-strip",
        "empty-output-collapse",
        "step-metadata-trim",
    ],
    "standard": [
        # gentle (superset)
        "compaction-marker-collapse",
        "stale-file-read-strip",
        "base64-image-strip",
        "empty-output-collapse",
        "step-metadata-trim",
        # standard additions
        "duplicate-tool-dedup",
        "error-input-purge",
        "reasoning-trim",
        "stale-snapshot-strip",
        "retry-metadata-strip",
        "patch-dedup",
    ],
    "aggressive": [
        # gentle
        "compaction-marker-collapse",
        "stale-file-read-strip",
        "base64-image-strip",
        "empty-output-collapse",
        "step-metadata-trim",
        # standard
        "duplicate-tool-dedup",
        "error-input-purge",
        "reasoning-trim",
        "stale-snapshot-strip",
        "retry-metadata-strip",
        "patch-dedup",
        # aggressive additions
        "old-context-drop",
        "large-output-truncate",
        "subtask-result-collapse",
        "file-content-summarize",
        "conversation-thinning",
    ],
}


StrategyFunc = Callable[
    [list["MessageInfo"], list["PartInfo"], "Config"],
    "StrategyResult",
]


def strategy(
    name: str,
    description: str,
    tier: str,
    expected_savings: str,
) -> Callable[[StrategyFunc], StrategyFunc]:
    """Decorator that registers a pruning strategy."""

    def decorator(func: StrategyFunc) -> StrategyFunc:
        STRATEGIES[name] = StrategyInfo(
            name=name,
            description=description,
            tier=tier,
            expected_savings=expected_savings,
            func=func,
        )
        return func

    return decorator
