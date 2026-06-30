"""Layered configuration: env var > config file > defaults."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from headroom_cli._constants import (
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MAX_DROP_PCT,
    DEFAULT_PRESERVE_LAST_K,
    SYSTEM_OVERHEAD_TOKENS,
)

CONFIG_DIR = Path.home() / ".headroom-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass(frozen=True)
class FloorConfig:
    """Safety floors — hard limits on how much pruning can remove."""

    max_message_drop_pct: float = DEFAULT_MAX_DROP_PCT
    preserve_last_k_turns: int = DEFAULT_PRESERVE_LAST_K
    preserve_first_message: bool = True


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    floor: FloorConfig = field(default_factory=FloorConfig)
    context_window: int = DEFAULT_CONTEXT_WINDOW
    system_overhead_tokens: int = SYSTEM_OVERHEAD_TOKENS


def _read_config_file() -> dict[str, object]:
    """Read JSON config file if it exists."""
    if not CONFIG_FILE.is_file():
        return {}
    try:
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _env_int(key: str) -> int | None:
    val = os.environ.get(key)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _env_float(key: str) -> float | None:
    val = os.environ.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def load_config() -> Config:
    """Load config with precedence: env var > config file > defaults."""
    file_data = _read_config_file()
    file_floor = file_data.get("floor", {})
    if not isinstance(file_floor, dict):
        file_floor = {}

    # Context window
    context_window = (
        _env_int("HEADROOM_CLI_CONTEXT_WINDOW")
        or _safe_int(file_data.get("context_window"))
        or DEFAULT_CONTEXT_WINDOW
    )

    # Floor: max drop pct
    max_drop = (
        _env_float("HEADROOM_CLI_FLOOR_MAX_DROP_PCT")
        or _safe_float(file_floor.get("max_message_drop_pct"))
        or DEFAULT_MAX_DROP_PCT
    )

    # Floor: preserve last K
    preserve_k = (
        _env_int("HEADROOM_CLI_FLOOR_PRESERVE_LAST_K")
        or _safe_int(file_floor.get("preserve_last_k_turns"))
        or DEFAULT_PRESERVE_LAST_K
    )

    # Floor: preserve first
    preserve_first = True
    raw_first = file_floor.get("preserve_first_message")
    if isinstance(raw_first, bool):
        preserve_first = raw_first

    floor = FloorConfig(
        max_message_drop_pct=max_drop,
        preserve_last_k_turns=preserve_k,
        preserve_first_message=preserve_first,
    )

    return Config(
        floor=floor,
        context_window=context_window,
    )


def _safe_int(val: object) -> int | None:
    if isinstance(val, int):
        return val
    return None


def _safe_float(val: object) -> float | None:
    if isinstance(val, (int, float)):
        return float(val)
    return None


def ensure_config_dir() -> Path:
    """Create config directory if it does not exist. Returns the path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR
