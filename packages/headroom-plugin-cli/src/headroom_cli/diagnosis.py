"""Session diagnosis — bloat analysis by part type (generic version)."""
from __future__ import annotations

import json
from typing import Any

from headroom_cli._constants import (
    FILE_READ_TYPES,
    IMAGE_TYPES,
    METADATA_TYPES,
    REASONING_TYPES,
    TOOL_OUTPUT_TYPES,
)
from headroom_cli.types import MessageInfo


def analyze_bloat(messages: list[MessageInfo]) -> dict[str, Any]:
    """Analyze messages and return bloat breakdown by category."""
    # Flatten all parts
    all_parts = [part for msg in messages for part in msg.parts]
    
    total_bytes = sum(p.size_bytes for p in all_parts)

    # Categorize parts
    categories: dict[str, dict[str, int | float]] = {
        "tool_outputs": {"bytes": 0, "count": 0},
        "reasoning": {"bytes": 0, "count": 0},
        "file_reads": {"bytes": 0, "count": 0},
        "images": {"bytes": 0, "count": 0},
        "metadata": {"bytes": 0, "count": 0},
        "text": {"bytes": 0, "count": 0},
    }

    for part in all_parts:
        pt = part.type.lower()
        
        if pt in TOOL_OUTPUT_TYPES or pt == "tool_result":
            cat = "tool_outputs"
        elif pt in REASONING_TYPES:
            cat = "reasoning"
        elif pt in FILE_READ_TYPES:
            cat = "file_reads"
        elif pt in IMAGE_TYPES or _has_base64_content(part):
            cat = "images"
        elif pt in METADATA_TYPES:
            cat = "metadata"
        else:
            cat = "text"

        categories[cat]["bytes"] = int(categories[cat]["bytes"]) + part.size_bytes
        categories[cat]["count"] = int(categories[cat]["count"]) + 1

    # Compute percentages
    sources: list[dict[str, Any]] = []
    for cat_name, cat_data in categories.items():
        cat_bytes = int(cat_data["bytes"])
        if cat_bytes > 0:  # Only include non-empty categories
            sources.append({
                "category": cat_name,
                "size_bytes": cat_bytes,
                "count": int(cat_data["count"]),
                "percent": round((cat_bytes / total_bytes * 100) if total_bytes > 0 else 0.0, 1),
            })

    # Sort by size descending
    sources.sort(key=lambda x: x["size_bytes"], reverse=True)

    # Generate recommendations
    recommendations = _recommend_tier(sources, total_bytes)

    return {
        "sources": sources,
        "recommendations": recommendations,
    }


def _has_base64_content(part: Any) -> bool:
    """Check if part contains base64-encoded content."""
    # Check if content looks like base64
    if part.content and len(part.content) > 1000:
        alnum_ratio = sum(c.isalnum() or c in "+/=" for c in part.content) / len(part.content)
        return alnum_ratio > 0.85
    
    # Check output_data if present
    if part.output_data and len(part.output_data) > 1000:
        alnum_ratio = sum(c.isalnum() or c in "+/=" for c in part.output_data) / len(part.output_data)
        return alnum_ratio > 0.85
    
    return False


def _recommend_tier(
    sources: list[dict[str, Any]],
    total_bytes: int,
) -> list[str]:
    """Recommend prescription tiers based on bloat analysis."""
    recommendations: list[str] = []

    # Build a lookup
    breakdown = {s["category"]: s["percent"] for s in sources}

    # Always recommend gentle — it's safe
    recommendations.append("Apply 'gentle' prescription to remove stale tool calls")

    # If images or metadata are > 10%, or tool outputs > 30%, suggest standard
    img_pct = breakdown.get("images", 0)
    meta_pct = breakdown.get("metadata", 0)
    tool_pct = breakdown.get("tool_outputs", 0)
    reasoning_pct = breakdown.get("reasoning", 0)

    if img_pct > 10 or meta_pct > 10 or tool_pct > 30 or reasoning_pct > 15:
        recommendations.append("Consider 'standard' for duplicate content cleanup")

    # If tool outputs dominate, suggest aggressive
    if tool_pct > 50 or total_bytes > 500_000:
        recommendations.append("'aggressive' may be needed for heavy tool output bloat")

    return recommendations
