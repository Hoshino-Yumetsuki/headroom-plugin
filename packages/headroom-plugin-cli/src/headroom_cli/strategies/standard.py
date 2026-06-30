"""Standard strategies — moderate pruning, adds on top of gentle."""
from __future__ import annotations

import json

from headroom_cli.config import Config
from headroom_cli.registry import strategy
from headroom_cli.strategies._config import ERROR_TURN_AGE, REASONING_KEEP_CHARS
from headroom_cli.types import MessageInfo, PartInfo, PruneAction, StrategyResult


@strategy(
    name="duplicate-tool-dedup",
    description="Keep only most recent of identical tool calls",
    tier="standard",
    expected_savings="5-15%",
)
def duplicate_tool_dedup(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Deduplicate identical tool calls (same tool + same params)."""
    actions: list[PruneAction] = []

    # Build fingerprint for tool-call parts
    seen: dict[str, PartInfo] = {}  # fingerprint -> latest part
    duplicates: list[PartInfo] = []

    sorted_parts = sorted(parts, key=lambda p: p.time_created)
    for part in sorted_parts:
        if part.part_type not in {"tool-call", "tool_call", "tool-use", "tool_use"}:
            continue
        fp = _tool_fingerprint(part.data)
        if fp is None:
            continue
        if fp in seen:
            duplicates.append(seen[fp])
        seen[fp] = part

    for dup in duplicates:
        actions.append(PruneAction(
            part_id=dup.id,
            message_id=dup.message_id,
            action="remove",
            reason="Duplicate tool call",
            original_bytes=dup.byte_size,
            pruned_bytes=0,
        ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="duplicate-tool-dedup",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="error-input-purge",
    description="Replace errored tool inputs with placeholder after N turns",
    tier="standard",
    expected_savings="2-10%",
)
def error_input_purge(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """After ERROR_TURN_AGE turns, replace errored tool inputs with placeholder."""
    actions: list[PruneAction] = []
    sorted_msgs = sorted(messages, key=lambda m: m.time_created)
    total_turns = len(sorted_msgs)

    # Find messages with error tool results
    error_msg_ids: set[str] = set()
    for part in parts:
        if part.part_type in {"tool-result", "tool_result"}:
            if _is_error_result(part.data):
                error_msg_ids.add(part.message_id)

    # Map message_id -> turn index
    msg_turn: dict[str, int] = {m.id: i for i, m in enumerate(sorted_msgs)}

    for part in parts:
        if part.part_type not in {"tool-call", "tool_call", "tool-use", "tool_use"}:
            continue
        if part.message_id not in error_msg_ids:
            continue
        turn = msg_turn.get(part.message_id, total_turns)
        age = total_turns - turn
        if age < ERROR_TURN_AGE:
            continue

        placeholder = {"content": "[errored tool input removed]"}
        pruned_bytes = len(json.dumps(placeholder).encode("utf-8"))
        actions.append(PruneAction(
            part_id=part.id,
            message_id=part.message_id,
            action="replace",
            reason=f"Errored tool input ({age} turns ago)",
            original_bytes=part.byte_size,
            pruned_bytes=pruned_bytes,
            replacement=placeholder,
        ))

    total_saved = sum(a.original_bytes - a.pruned_bytes for a in actions)
    return StrategyResult(
        name="error-input-purge",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="reasoning-trim",
    description="Truncate thinking/reasoning blocks to first N chars",
    tier="standard",
    expected_savings="5-20%",
)
def reasoning_trim(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Truncate reasoning/thinking blocks to first REASONING_KEEP_CHARS."""
    actions: list[PruneAction] = []

    for part in parts:
        if part.part_type not in {"thinking", "reasoning"}:
            continue
        content = _extract_text(part.data)
        if content is None or len(content) <= REASONING_KEEP_CHARS:
            continue

        truncated = content[:REASONING_KEEP_CHARS] + "... [truncated]"
        new_data = dict(part.data)
        _set_text(new_data, truncated)
        pruned_bytes = len(json.dumps(new_data, separators=(",", ":")).encode("utf-8"))

        actions.append(PruneAction(
            part_id=part.id,
            message_id=part.message_id,
            action="truncate",
            reason=f"Reasoning block ({len(content)} chars -> {REASONING_KEEP_CHARS})",
            original_bytes=part.byte_size,
            pruned_bytes=pruned_bytes,
            replacement=new_data,
        ))

    total_saved = sum(a.original_bytes - a.pruned_bytes for a in actions)
    return StrategyResult(
        name="reasoning-trim",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="stale-snapshot-strip",
    description="Remove old git snapshot parts, keep only latest",
    tier="standard",
    expected_savings="2-10%",
)
def stale_snapshot_strip(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Remove old git/code snapshot parts, keeping only the latest."""
    actions: list[PruneAction] = []
    snapshot_types = {"git-snapshot", "git_snapshot", "snapshot", "code-snapshot"}

    snapshots: list[PartInfo] = []
    for part in parts:
        if part.part_type in snapshot_types:
            snapshots.append(part)

    if len(snapshots) < 2:
        return StrategyResult(name="stale-snapshot-strip")

    sorted_snaps = sorted(snapshots, key=lambda p: p.time_created)
    for stale in sorted_snaps[:-1]:
        actions.append(PruneAction(
            part_id=stale.id,
            message_id=stale.message_id,
            action="remove",
            reason="Stale snapshot",
            original_bytes=stale.byte_size,
            pruned_bytes=0,
        ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="stale-snapshot-strip",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="retry-metadata-strip",
    description="Remove retry metadata parts",
    tier="standard",
    expected_savings="1-3%",
)
def retry_metadata_strip(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Remove retry-metadata parts."""
    actions: list[PruneAction] = []

    for part in parts:
        if part.part_type in {"retry-metadata", "retry_metadata"}:
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="remove",
                reason="Retry metadata",
                original_bytes=part.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="retry-metadata-strip",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="patch-dedup",
    description="Deduplicate identical patch parts",
    tier="standard",
    expected_savings="1-5%",
)
def patch_dedup(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Deduplicate identical patch/diff parts."""
    actions: list[PruneAction] = []

    seen: dict[str, PartInfo] = {}  # content hash -> latest part
    duplicates: list[PartInfo] = []

    sorted_parts = sorted(parts, key=lambda p: p.time_created)
    for part in sorted_parts:
        if part.part_type not in {"patch", "diff", "edit"}:
            continue
        content = json.dumps(part.data, separators=(",", ":"), sort_keys=True)
        if content in seen:
            duplicates.append(seen[content])
        seen[content] = part

    for dup in duplicates:
        actions.append(PruneAction(
            part_id=dup.id,
            message_id=dup.message_id,
            action="remove",
            reason="Duplicate patch",
            original_bytes=dup.byte_size,
            pruned_bytes=0,
        ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="patch-dedup",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


# --- Helpers ---

def _tool_fingerprint(data: dict[str, object]) -> str | None:
    """Create a fingerprint for a tool call from its name + args."""
    name = data.get("name") or data.get("tool") or data.get("toolName")
    args = data.get("args") or data.get("arguments") or data.get("input")
    if not name:
        return None
    args_str = json.dumps(args, separators=(",", ":"), sort_keys=True, default=str)
    return f"{name}:{args_str}"


def _is_error_result(data: dict[str, object]) -> bool:
    """Check if a tool result indicates an error."""
    if data.get("isError") or data.get("is_error"):
        return True
    content = _extract_text(data)
    if content and any(kw in content.lower() for kw in ("error", "traceback", "exception")):
        return True
    return False


def _extract_text(data: dict[str, object]) -> str | None:
    """Extract text content from data."""
    for key in ("content", "text", "output", "thinking", "reasoning"):
        val = data.get(key)
        if isinstance(val, str):
            return val
    return None


def _set_text(data: dict[str, object], text: str) -> None:
    """Set text content in data, using the first matching key."""
    for key in ("content", "text", "output", "thinking", "reasoning"):
        if key in data:
            data[key] = text
            return
    data["content"] = text
