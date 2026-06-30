"""Simple compression API using headroom SDK."""

from __future__ import annotations

from typing import Any

from headroom import compress as headroom_compress, CompressConfig


def compress(request: dict[str, Any]) -> dict[str, Any]:
    """
    Compress messages using headroom SDK.
    
    Accepts standard Anthropic/OpenAI format messages.
    
    Args:
        request: {
            "messages": [...],  # Anthropic/OpenAI format
            "prescription": "gentle" | "standard" | "aggressive",
            "model": "claude-sonnet-4",  # Optional
            "context_window": 200000  # Optional
        }
    
    Returns:
        {
            "status": "success",
            "messages": [...],  # Compressed messages
            "tokens_before": 1000,
            "tokens_after": 600,
            "tokens_saved": 400,
            "compression_ratio": 0.4
        }
    """
    try:
        messages = request.get("messages", [])
        prescription = request.get("prescription", "gentle")
        model = request.get("model", "claude-sonnet-4-5-20250929")
        context_window = request.get("context_window", 200000)
        
        # Map prescription to headroom config
        config = _get_headroom_config(prescription)
        
        # Call headroom SDK
        result = headroom_compress(
            messages=messages,
            model=model,
            model_limit=context_window,
            optimize=True,
            config=config,
        )
        
        return {
            "status": "success",
            "messages": result.messages,
            "tokens_before": result.tokens_before,
            "tokens_after": result.tokens_after,
            "tokens_saved": result.tokens_saved,
            "compression_ratio": result.compression_ratio,
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }


def _get_headroom_config(prescription: str) -> CompressConfig:
    """Map prescription to headroom CompressConfig."""
    
    configs = {
        "gentle": CompressConfig(
            target_ratio=0.7,
            compress_user_messages=False,
            protect_recent=3,
        ),
        "standard": CompressConfig(
            target_ratio=0.5,
            compress_user_messages=False,
            protect_recent=2,
        ),
        "aggressive": CompressConfig(
            target_ratio=0.3,
            compress_user_messages=True,
            protect_recent=1,
        ),
    }
    
    return configs.get(prescription, configs["gentle"])
