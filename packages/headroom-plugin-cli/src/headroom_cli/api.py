"""Generic context compression API - client-agnostic."""

from __future__ import annotations

from typing import Any

from headroom_cli.diagnosis import analyze_bloat
from headroom_cli.registry import get_prescription_strategies
from headroom_cli.types import MessageInfo, PartInfo


def compress(request: dict[str, Any]) -> dict[str, Any]:
    """
    Compress a session based on the request.

    Args:
        request: {
            "command": "compress",
            "prescription": "gentle" | "standard" | "aggressive",
            "session": {
                "id": "ses_abc123",
                "context_window": 200000,
                "current_usage": 150000
            },
            "messages": [...]
        }

    Returns:
        {
            "status": "success",
            "summary": {
                "original_size": 150000,
                "compressed_size": 95000,
                "savings_bytes": 55000,
                "savings_percent": 36.7
            },
            "actions": [...]
        }
    """
    try:
        prescription = request.get("prescription", "gentle")
        messages_data = request.get("messages", [])

        # Convert input format to internal MessageInfo
        messages = _parse_messages(messages_data)

        # Get strategies for prescription
        strategy_names = get_prescription_strategies(prescription)

        # Calculate original size
        original_size = sum(
            sum(p.size_bytes for p in msg.parts) for msg in messages
        )

        # Apply strategies and collect actions
        actions: list[dict[str, Any]] = []
        parts_to_delete: set[str] = set()

        for strategy_name in strategy_names:
            try:
                # Import strategy dynamically
                strategy_module = __import__(
                    f"headroom_cli.strategies.{strategy_name.replace('-', '_')}",
                    fromlist=["find_parts_to_prune"],
                )
                
                # Call the strategy
                if hasattr(strategy_module, "find_parts_to_prune"):
                    prune_list = strategy_module.find_parts_to_prune(messages)
                    
                    for part_id in prune_list:
                        if part_id not in parts_to_delete:
                            parts_to_delete.add(part_id)
                            
                            # Find the part to get its size
                            for msg in messages:
                                for part in msg.parts:
                                    if part.id == part_id:
                                        actions.append({
                                            "action": "delete_part",
                                            "part_id": part_id,
                                            "reason": f"Removed by {strategy_name}",
                                            "strategy": strategy_name,
                                            "savings_bytes": part.size_bytes,
                                        })
                                        break
            except (ImportError, AttributeError) as e:
                # Skip strategies that don't exist or don't have the right function
                continue

        # Calculate compressed size
        compressed_size = original_size - sum(a["savings_bytes"] for a in actions)
        savings_bytes = original_size - compressed_size
        savings_percent = (savings_bytes / original_size * 100) if original_size > 0 else 0

        return {
            "status": "success",
            "summary": {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "savings_bytes": savings_bytes,
                "savings_percent": round(savings_percent, 1),
            },
            "actions": actions,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "details": type(e).__name__,
        }


def diagnose(request: dict[str, Any]) -> dict[str, Any]:
    """
    Diagnose bloat sources in a session.

    Args:
        request: {
            "command": "diagnose",
            "messages": [...]
        }

    Returns:
        {
            "status": "success",
            "bloat_sources": [...],
            "recommendations": [...]
        }
    """
    try:
        messages_data = request.get("messages", [])
        messages = _parse_messages(messages_data)

        # Analyze bloat
        bloat = analyze_bloat(messages)

        return {
            "status": "success",
            "bloat_sources": bloat["sources"],
            "recommendations": bloat["recommendations"],
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "details": type(e).__name__,
        }


def _parse_messages(messages_data: list[dict[str, Any]]) -> list[MessageInfo]:
    """Convert input JSON format to internal MessageInfo objects."""
    messages: list[MessageInfo] = []

    for msg_data in messages_data:
        parts: list[PartInfo] = []

        for part_data in msg_data.get("parts", []):
            part = PartInfo(
                id=part_data["id"],
                type=part_data["type"],
                content=part_data.get("content"),
                tool=part_data.get("tool"),
                input_data=part_data.get("input"),
                output_data=part_data.get("output"),
                size_bytes=part_data.get("size_bytes", 0),
            )
            parts.append(part)

        message = MessageInfo(
            id=msg_data["id"],
            role=msg_data["role"],
            timestamp=msg_data.get("timestamp", 0),
            parts=parts,
        )
        messages.append(message)

    return messages
