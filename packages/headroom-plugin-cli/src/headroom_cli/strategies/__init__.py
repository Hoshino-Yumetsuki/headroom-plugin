"""Auto-register all strategy modules on import."""
from __future__ import annotations

# Importing these modules triggers the @strategy decorators,
# which populate registry.STRATEGIES.
from headroom_cli.strategies import aggressive as _aggressive  # noqa: F401
from headroom_cli.strategies import gentle as _gentle  # noqa: F401
from headroom_cli.strategies import standard as _standard  # noqa: F401
