"""Execute pruning actions against the OpenCode database."""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from headroom_cli._constants import BACKUP_SUFFIX
from headroom_cli.config import Config
from headroom_cli.helpers import emit, format_bytes
from headroom_cli.registry import PRESCRIPTIONS, STRATEGIES
from headroom_cli.safety import validate_actions
from headroom_cli.session import get_session_data
from headroom_cli.types import PrescriptionResult, PruneAction, StrategyResult


def execute_actions(
    db_path: Path,
    session_id: str,
    actions: list[PruneAction],
    *,
    dry_run: bool = True,
) -> int:
    """Execute prune actions against the database. Returns bytes saved."""
    if not actions:
        return 0

    total_saved = 0
    for action in actions:
        match action.action:
            case "remove":
                total_saved += action.original_bytes
            case "replace" | "truncate":
                total_saved += action.original_bytes - action.pruned_bytes

    if dry_run:
        return total_saved

    # Create backup before modifying
    backup_path = Path(str(db_path) + BACKUP_SUFFIX)
    shutil.copy2(db_path, backup_path)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        for action in actions:
            match action.action:
                case "remove":
                    conn.execute(
                        "DELETE FROM part WHERE id = ?",
                        (action.part_id,),
                    )
                case "replace" | "truncate":
                    if action.replacement is not None:
                        new_data = json.dumps(
                            action.replacement,
                            separators=(",", ":"),
                            default=str,
                        )
                        conn.execute(
                            "UPDATE part SET data = ? WHERE id = ?",
                            (new_data, action.part_id),
                        )
        conn.commit()
        # Checkpoint WAL
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    except Exception:
        conn.rollback()
        # Restore backup on failure
        shutil.copy2(backup_path, db_path)
        raise
    finally:
        conn.close()

    return total_saved


def run_prescription(
    db_path: Path,
    session_id: str,
    rx_name: str,
    config: Config,
    *,
    dry_run: bool = True,
) -> PrescriptionResult:
    """Run a full prescription (ordered list of strategies)."""
    strategy_names = PRESCRIPTIONS.get(rx_name)
    if strategy_names is None:
        msg = f"Unknown prescription: {rx_name}"
        raise ValueError(msg)

    messages, parts = get_session_data(db_path, session_id)

    result = PrescriptionResult(prescription=rx_name)
    all_actions: list[PruneAction] = []
    already_acted: set[str] = set()  # part IDs already targeted

    for strategy_name in strategy_names:
        info = STRATEGIES.get(strategy_name)
        if info is None:
            emit(f"  Warning: strategy '{strategy_name}' not registered, skipping")
            continue

        strat_result: StrategyResult = info.func(messages, parts, config)  # type: ignore[operator]

        # Filter out actions on parts already targeted by earlier strategies
        filtered: list[PruneAction] = []
        for action in strat_result.actions:
            if action.part_id not in already_acted:
                filtered.append(action)
                already_acted.add(action.part_id)

        strat_result.actions = filtered
        strat_result.parts_affected = len(filtered)
        strat_result.bytes_saved = sum(
            a.original_bytes - a.pruned_bytes
            if a.action in ("replace", "truncate")
            else a.original_bytes
            for a in filtered
        )

        result.strategies.append(strat_result)
        all_actions.extend(filtered)

    result.total_bytes_saved = sum(s.bytes_saved for s in result.strategies)
    result.total_parts_affected = sum(s.parts_affected for s in result.strategies)

    # Validate safety floors
    validate_actions(all_actions, messages, parts, config)

    # Execute
    if not dry_run:
        execute_actions(db_path, session_id, all_actions, dry_run=False)
        emit(f"  Applied: {format_bytes(result.total_bytes_saved)} saved")

    return result
