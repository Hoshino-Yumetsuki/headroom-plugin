"""Session diagnosis — bloat analysis by part type."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from headroom_cli._constants import (
    FILE_READ_TYPES,
    IMAGE_TYPES,
    METADATA_TYPES,
    REASONING_TYPES,
    TOOL_OUTPUT_TYPES,
)
from headroom_cli.session import get_session_data
from headroom_cli.tokens import estimate_session_tokens


def diagnose_session(db_path: Path, session_id: str) -> dict[str, Any]:
    """Analyze a session and return bloat breakdown by category."""
    messages, parts = get_session_data(db_path, session_id)

    total_bytes = sum(p.byte_size for p in parts)

    # Categorize parts
    categories: dict[str, dict[str, int | float]] = {
        "tool_outputs": {"bytes": 0, "count": 0},
        "reasoning": {"bytes": 0, "count": 0},
        "file_reads": {"bytes": 0, "count": 0},
        "images": {"bytes": 0, "count": 0},
        "metadata": {"bytes": 0, "count": 0},
        "text": {"bytes": 0, "count": 0},
    }

    for part in parts:
        pt = part.part_type.lower()
        if pt in TOOL_OUTPUT_TYPES:
            cat = "tool_outputs"
        elif pt in REASONING_TYPES:
            cat = "reasoning"
        elif pt in FILE_READ_TYPES:
            cat = "file_reads"
        elif pt in IMAGE_TYPES or _has_base64(part.data):
            cat = "images"
        elif pt in METADATA_TYPES:
            cat = "metadata"
        else:
            cat = "text"

        categories[cat]["bytes"] = int(categories[cat]["bytes"]) + part.byte_size
        categories[cat]["count"] = int(categories[cat]["count"]) + 1

    # Compute percentages
    breakdown: dict[str, dict[str, int | float]] = {}
    for cat_name, cat_data in categories.items():
        cat_bytes = int(cat_data["bytes"])
        breakdown[cat_name] = {
            "bytes": cat_bytes,
            "count": int(cat_data["count"]),
            "pct": (cat_bytes / total_bytes * 100) if total_bytes > 0 else 0.0,
        }

    # Recommend prescription tier
    estimated_tokens = estimate_session_tokens(messages, parts)
    recommendations = _recommend_tier(breakdown, estimated_tokens)

    return {
        "session_id": session_id,
        "total_bytes": total_bytes,
        "total_parts": len(parts),
        "total_messages": len(messages),
        "estimated_tokens": estimated_tokens,
        "breakdown": breakdown,
        "recommendations": recommendations,
    }


def _has_base64(data: dict[str, object]) -> bool:
    """Check if data contains base64-encoded content."""
    raw = json.dumps(data, separators=(",", ":"), default=str)
    # Base64 heuristic: long strings of alphanumerics with padding
    if len(raw) > 1000:
        alnum_ratio = sum(c.isalnum() or c in "+/=" for c in raw) / len(raw)
        return alnum_ratio > 0.85
    return False


def _recommend_tier(
    breakdown: dict[str, dict[str, int | float]],
    estimated_tokens: int,
) -> list[str]:
    """Recommend prescription tiers based on bloat analysis."""
    recommendations: list[str] = []

    # Always recommend gentle — it's safe
    recommendations.append("gentle")

    # If images or metadata are > 10%, or tool outputs > 30%, suggest standard
    img_pct = float(breakdown.get("images", {}).get("pct", 0))
    meta_pct = float(breakdown.get("metadata", {}).get("pct", 0))
    tool_pct = float(breakdown.get("tool_outputs", {}).get("pct", 0))
    reasoning_pct = float(breakdown.get("reasoning", {}).get("pct", 0))

    if img_pct > 10 or meta_pct > 10 or tool_pct > 30 or reasoning_pct > 15:
        recommendations.append("standard")

    # If estimated tokens > 100K or tool outputs dominate, suggest aggressive
    if estimated_tokens > 100_000 or tool_pct > 50:
        recommendations.append("aggressive")

    return recommendations
