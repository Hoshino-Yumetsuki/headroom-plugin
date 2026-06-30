"""Gentle strategies — safe, always-win pruning."""
from __future__ import annotations

import json
import re

from headroom_cli.config import Config
from headroom_cli.registry import strategy
from headroom_cli.strategies._config import COMPACTION_MARKER_TEXT
from headroom_cli.types import MessageInfo, PartInfo, PruneAction, StrategyResult


@strategy(
    name="compaction-marker-collapse",
    description="Remove pre-compaction messages when compaction marker exists",
    tier="gentle",
    expected_savings="10-40%",
)
def compaction_marker_collapse(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Find compaction markers and remove all parts from messages before them."""
    actions: list[PruneAction] = []
    sorted_msgs = sorted(messages, key=lambda m: m.time_created)

    # Find compaction marker message
    marker_idx: int | None = None
    for i, msg in enumerate(sorted_msgs):
        data_str = json.dumps(msg.data, default=str).lower()
        if COMPACTION_MARKER_TEXT in data_str:
            marker_idx = i
            break

    if marker_idx is None:
        return StrategyResult(name="compaction-marker-collapse")

    # Collect message IDs before the marker
    pre_marker_ids = {m.id for m in sorted_msgs[:marker_idx]}

    for part in parts:
        if part.message_id in pre_marker_ids:
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="remove",
                reason="Pre-compaction message",
                original_bytes=part.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="compaction-marker-collapse",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="stale-file-read-strip",
    description="When same file read multiple times, keep only latest",
    tier="gentle",
    expected_savings="5-20%",
)
def stale_file_read_strip(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Deduplicate file reads — keep only the latest read per file path."""
    actions: list[PruneAction] = []

    # Group file-read parts by path, track order
    file_reads: dict[str, list[PartInfo]] = {}
    for part in parts:
        if part.part_type in {"file-read", "file_read", "read-file"}:
            path = _extract_file_path(part.data)
            if path:
                file_reads.setdefault(path, []).append(part)

    # For each file read more than once, remove all but the latest
    for path, read_parts in file_reads.items():
        if len(read_parts) < 2:
            continue
        sorted_reads = sorted(read_parts, key=lambda p: p.time_created)
        for stale in sorted_reads[:-1]:
            actions.append(PruneAction(
                part_id=stale.id,
                message_id=stale.message_id,
                action="remove",
                reason=f"Stale file read: {path}",
                original_bytes=stale.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="stale-file-read-strip",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="base64-image-strip",
    description="Replace base64-encoded images with placeholder",
    tier="gentle",
    expected_savings="5-30%",
)
def base64_image_strip(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Replace base64 image data with a size placeholder."""
    actions: list[PruneAction] = []
    b64_pattern = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]{100,}")

    for part in parts:
        raw = json.dumps(part.data, separators=(",", ":"), default=str)
        match = b64_pattern.search(raw)
        if match:
            img_bytes = len(match.group())
            placeholder = f"[image: {img_bytes} bytes removed]"
            new_data = b64_pattern.sub(placeholder, raw)
            pruned_bytes = len(new_data.encode("utf-8"))
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="replace",
                reason="Base64 image data",
                original_bytes=part.byte_size,
                pruned_bytes=pruned_bytes,
                replacement=json.loads(new_data),
            ))

    total_saved = sum(a.original_bytes - a.pruned_bytes for a in actions)
    return StrategyResult(
        name="base64-image-strip",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="empty-output-collapse",
    description="Remove tool calls with empty/whitespace-only output",
    tier="gentle",
    expected_savings="1-5%",
)
def empty_output_collapse(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Remove parts that are tool results with empty or whitespace-only content."""
    actions: list[PruneAction] = []

    for part in parts:
        if part.part_type not in {"tool-result", "tool_result"}:
            continue
        content = _extract_content(part.data)
        if content is not None and content.strip() == "":
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="remove",
                reason="Empty tool output",
                original_bytes=part.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="empty-output-collapse",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


@strategy(
    name="step-metadata-trim",
    description="Strip step-start/step-finish timing parts",
    tier="gentle",
    expected_savings="1-3%",
)
def step_metadata_trim(
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> StrategyResult:
    """Remove step-start and step-finish parts that just track timing."""
    actions: list[PruneAction] = []
    step_types = {"step-start", "step-finish", "step_start", "step_finish"}

    for part in parts:
        if part.part_type in step_types:
            actions.append(PruneAction(
                part_id=part.id,
                message_id=part.message_id,
                action="remove",
                reason=f"Step metadata: {part.part_type}",
                original_bytes=part.byte_size,
                pruned_bytes=0,
            ))

    total_saved = sum(a.original_bytes for a in actions)
    return StrategyResult(
        name="step-metadata-trim",
        actions=actions,
        bytes_saved=total_saved,
        parts_affected=len(actions),
    )


# --- Helpers ---

def _extract_file_path(data: dict[str, object]) -> str | None:
    """Extract file path from a file-read part's data."""
    for key in ("path", "file", "filePath", "file_path"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    # Try nested
    content = data.get("content")
    if isinstance(content, dict):
        return _extract_file_path(content)
    return None


def _extract_content(data: dict[str, object]) -> str | None:
    """Extract text content from a part's data."""
    for key in ("content", "text", "output", "result"):
        val = data.get(key)
        if isinstance(val, str):
            return val
    return None
