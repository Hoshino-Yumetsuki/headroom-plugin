"""Aggressive strategies — heavy pruning, adds on top of standard."""
from __future__ import annotations

import json

from headroom_cli.config import Config
from headroom_cli.registry import strategy
from headroom_cli.strategies._config import (
    LARGE_OUTPUT_KEEP_CHARS,
    LARGE_OUTPUT_THRESHOLD,
    OLD_CONTEXT_DEFAULT_K,
    THINNING_KEEP_RATIO,
)
from headroom_cli.types import MessageInfo, PartInfo, PruneAction, StrategyResult


@strategy(
    name="old-context-drop",
    description="Drop messages beyond last K turns",
    tier="aggressive",
    expected_savings="20-50%",
)
def old_context_drop(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Drop all parts from messages beyond the last K turns."""
    actions: list[PruneAction] = []
    k = config.floor.preserve_last_k_turns or OLD_CONTEXT_DEFAULT_K
    sorted_msgs = sorted(messages, key=lambda m: m.time_created)

    if len(sorted_msgs) <= k:
        return StrategyResult(name="old-context-drop")

    # Preserve first message if configured
    start_idx = 1 if config.floor.preserve_first_message else 0
    drop_ids = {m.id for m in sorted_msgs[start_idx : -k]}

    for part in parts:
        if part.message_id in drop_ids:
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="remove",
                reason="Old context (beyond last K turns)",
                original_bytes=part.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="old-context-drop",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="large-output-truncate",
    description="Truncate tool outputs > N bytes",
    tier="aggressive",
    expected_savings="10-30%",
)
def large_output_truncate(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Truncate large tool outputs to first N chars + [truncated] marker."""
    actions: list[PruneAction] = []

    for part in parts:
        if part.part_type not in {"tool-result", "tool_result"}:
            continue
        if part.byte_size <= LARGE_OUTPUT_THRESHOLD:
            continue

        content = _extract_text(part.data)
        if content is None or len(content) <= LARGE_OUTPUT_KEEP_CHARS:
            continue

        truncated = content[:LARGE_OUTPUT_KEEP_CHARS] + f"\n[truncated: {len(content) - LARGE_OUTPUT_KEEP_CHARS} chars removed]"
        new_data = dict(part.data)
        _set_text(new_data, truncated)
        pruned_bytes = len(json.dumps(new_data, separators=(",", ":")).encode("utf-8"))

        actions.append(PruneAction(
            part_id=part.id,
            message_id=part.message_id,
            action="truncate",
            reason=f"Large tool output ({part.byte_size} bytes)",
            original_bytes=part.byte_size,
            pruned_bytes=pruned_bytes,
            replacement=new_data,
        ))

    total_saved = sum(a.original_bytes - a.pruned_bytes for a in actions)
    return StrategyResult(
        name="large-output-truncate",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="subtask-result-collapse",
    description="Collapse completed subtask parts to summary",
    tier="aggressive",
    expected_savings="5-15%",
)
def subtask_result_collapse(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Collapse completed subtask/subagent result parts to a short summary."""
    actions: list[PruneAction] = []
    subtask_types = {"subtask-result", "subtask_result", "subagent-result", "subagent_result"}

    for part in parts:
        if part.part_type not in subtask_types:
            continue
        if part.byte_size <= 256:
            continue

        # Extract a summary line
        content = _extract_text(part.data)
        summary_line = ""
        if content:
            first_line = content.split("\n", 1)[0][:120]
            summary_line = first_line

        summary_data = {
            "content": f"[subtask completed: {summary_line}]",
            "collapsed": True,
        }
        pruned_bytes = len(json.dumps(summary_data, separators=(",", ":")).encode("utf-8"))

        actions.append(PruneAction(
            part_id=part.id,
            message_id=part.message_id,
            action="replace",
            reason="Subtask result collapsed",
            original_bytes=part.byte_size,
            pruned_bytes=pruned_bytes,
            replacement=summary_data,
        ))

    total_saved = sum(a.original_bytes - a.pruned_bytes for a in actions)
    return StrategyResult(
        name="subtask-result-collapse",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="file-content-summarize",
    description="Replace large file reads with summary placeholder",
    tier="aggressive",
    expected_savings="10-25%",
)
def file_content_summarize(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Replace large file-read contents with a size/path placeholder."""
    actions: list[PruneAction] = []

    for part in parts:
        if part.part_type not in {"file-read", "file_read", "read-file"}:
            continue
        if part.byte_size <= 1024:
            continue

        path = _extract_file_path(part.data)
        content = _extract_text(part.data)
        line_count = content.count("\n") + 1 if content else 0
        path_display = path or "unknown"

        summary_data = {
            "content": f"[file: {path_display}, {line_count} lines, {part.byte_size} bytes]",
            "summarized": True,
        }
        pruned_bytes = len(json.dumps(summary_data, separators=(",", ":")).encode("utf-8"))

        actions.append(PruneAction(
            part_id=part.id,
            message_id=part.message_id,
            action="replace",
            reason=f"Large file read: {path_display}",
            original_bytes=part.byte_size,
            pruned_bytes=pruned_bytes,
            replacement=summary_data,
        ))

    total_saved = sum(a.original_bytes - a.pruned_bytes for a in actions)
    return StrategyResult(
        name="file-content-summarize",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="conversation-thinning",
    description="Remove alternating assistant messages from old turns",
    tier="aggressive",
    expected_savings="10-30%",
)
def conversation_thinning(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Thin old conversation by removing every other assistant message."""
    actions: list[PruneAction] = []
    k = config.floor.preserve_last_k_turns or OLD_CONTEXT_DEFAULT_K
    sorted_msgs = sorted(messages, key=lambda m: m.time_created)

    if len(sorted_msgs) <= k:
        return StrategyResult(name="conversation-thinning")

    # Preserve first message if configured
    start_idx = 1 if config.floor.preserve_first_message else 0
    old_msgs = sorted_msgs[start_idx : -k]

    # Find assistant messages in old region, remove every other one
    assistant_msgs = [m for m in old_msgs if m.role == "assistant"]
    # Keep ratio: remove ~50% of assistant messages
    step = max(1, int(1 / (1 - THINNING_KEEP_RATIO)))
    drop_ids: set[str] = set()
    for i, msg in enumerate(assistant_msgs):
        if i % step == 0:
            drop_ids.add(msg.id)

    for part in parts:
        if part.message_id in drop_ids:
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="remove",
                reason="Conversation thinning (old assistant message)",
                original_bytes=part.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="conversation-thinning",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


# --- Helpers ---

def _extract_text(data: dict[str, object]) -> str | None:
    """Extract text content from data."""
    for key in ("content", "text", "output", "result"):
        val = data.get(key)
        if isinstance(val, str):
            return val
    return None


def _set_text(data: dict[str, object], text: str) -> None:
    """Set text content in data."""
    for key in ("content", "text", "output", "result"):
        if key in data:
            data[key] = text
            return
    data["content"] = text


def _extract_file_path(data: dict[str, object]) -> str | None:
    """Extract file path from part data."""
    for key in ("path", "file", "filePath", "file_path"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    content = data.get("content")
    if isinstance(content, dict):
        return _extract_file_path(content)
    return None
