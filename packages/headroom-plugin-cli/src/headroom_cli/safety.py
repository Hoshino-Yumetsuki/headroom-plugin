"""Post-prune safety validation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from headroom_cli.config import Config
    from headroom_cli.types import MessageInfo, PartInfo, PruneAction


class PruneValidationError(Exception):
    """Raised when a pruning plan violates safety floors."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(f"Safety floor violations: {'; '.join(violations)}")


def validate_actions(
    actions: list[PruneAction],
    messages: list[MessageInfo],
    parts: list[PartInfo],
    config: Config,
) -> None:
    """Validate that proposed actions respect safety floors.

    Raises PruneValidationError if any floor is violated.
    """
    violations: list[str] = []

    # Build sets of affected message IDs
    removed_part_ids = {a.part_id for a in actions if a.action == "remove"}
    removed_message_ids = {a.message_id for a in actions if a.action == "remove"}

    # Count how many messages would be fully removed
    # (all their parts are in the remove set)
    parts_by_message: dict[str, list[PartInfo]] = {}
    for part in parts:
        parts_by_message.setdefault(part.message_id, []).append(part)

    fully_removed_messages = 0
    for msg_id, msg_parts in parts_by_message.items():
        if all(p.id in removed_part_ids for p in msg_parts):
            fully_removed_messages += 1

    # Check: max message drop percentage
    total_messages = len(messages)
    if total_messages > 0:
        drop_pct = fully_removed_messages / total_messages
        if drop_pct > config.floor.max_message_drop_pct:
            violations.append(
                f"Would drop {drop_pct:.0%} of messages "
                f"(limit: {config.floor.max_message_drop_pct:.0%})"
            )

    # Check: preserve last K turns
    if config.floor.preserve_last_k_turns > 0:
        sorted_msgs = sorted(messages, key=lambda m: m.time_created)
        protected_ids = {
            m.id for m in sorted_msgs[-config.floor.preserve_last_k_turns :]
        }
        touched_protected = removed_message_ids & protected_ids
        if touched_protected:
            violations.append(
                f"Would remove {len(touched_protected)} message(s) "
                f"within the last {config.floor.preserve_last_k_turns} turns"
            )

    # Check: preserve first message
    if config.floor.preserve_first_message and messages:
        sorted_msgs = sorted(messages, key=lambda m: m.time_created)
        first_id = sorted_msgs[0].id
        if first_id in removed_message_ids:
            violations.append("Would remove the first message (system/init)")

    if violations:
        raise PruneValidationError(violations)
