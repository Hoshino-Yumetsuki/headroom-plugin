# @q78kg/opencode-headroom

Real-time context pruning for OpenCode sessions — inspired by [cozempic](https://github.com/Ruya-AI/cozempic) and aligned with [headroom](https://github.com/headroomlabs-ai/headroom) reverse proxy behavior.

## Design Principles

This plugin follows the **transparency principle** of the headroom reverse proxy:

- **No metadata injection**: The plugin does not inject any visible content into messages sent to the LLM
- **Internal tracking only**: Message IDs and compression metadata are tracked internally
- **Non-invasive pruning**: Context cleanup happens transparently without modifying user or model messages
- **JSON structured logging**: Machine-readable logs with local timezone timestamps
- **External log rotation**: Date-based log files (YYYY-MM-DD.log) rely on external tools like logrotate

## Architecture

This monorepo contains two packages:

### 1. `headroom-plugin-cli` (Python)

Backend CLI tool for OpenCode session pruning. Uses stdlib-only (zero dependencies) for maximum portability.

### 2. `opencode-plugin` (TypeScript)

The OpenCode plugin implementation.

## Installation Guide

### Installing the Python CLI (`headroom-plugin-cli`)

Using `uv` (recommended):

```bash
uv tool install headroom-plugin-cli@git+https://github.com/Hoshino-Yumetsuki/headroom-plugin.git#subdirectory=packages/headroom-plugin-cli --upgrade
```

Using standard `pip`:

```bash
pip install headroom-plugin-cli@git+https://github.com/Hoshino-Yumetsuki/headroom-plugin.git#subdirectory=packages/headroom-plugin-cli --upgrade
```

### Installing the OpenCode Plugin

Using the OpenCode CLI:

```bash
opencode plugin add @q78kg/opencode-headroom
```

## Configuration (Optional)

### OpenCode

Global config at `~/.config/opencode/headroom.jsonc`:

```jsonc
{
  "enabled": true,
  "compress": {
    "mode": "range",
    "maxContextLimit": 100000,
    "minContextLimit": 50000,
    "nudgeFrequency": 5,
    "protectedTools": ["task", "skill", "todowrite", "todoread"],
    "protectUserMessages": false
  },
  "strategies": {
    "deduplication": { "enabled": true },
    "purgeErrors": { "enabled": true, "turns": 4 },
    "staleContext": { "enabled": true }
  },
  "cli": {
    "path": "headroom-plugin-cli",
    "prescription": "gentle"
  },
  "log": {
    "debug": false,
    "info": true,
    "path": "~/.config/opencode/logs/headroom"
  }
}
```

Project config at `.opencode/headroom.jsonc` (overrides global).

## How It Works

1. **OpenCode Plugin** hooks into message transforms before sending to LLM
2. **Message Pipeline**: Filter → Assign IDs → Run strategies → Apply compression → Prune parts → Inject nudges
3. **Strategies** prune duplicate tool calls, old errors, stale file reads
4. **Compress Tool** allows model to summarize message ranges into compact blocks
5. **Nudge System** guides model toward compression at appropriate intervals
6. **Python CLI** can operate on session files directly (offline pruning)

## Pruning Strategies

### Gentle Tier (5 strategies)

- `compaction-collapse` - Collapse compaction markers
- `stale-file` - Remove superseded file reads
- `base64-strip` - Strip large base64 data
- `empty-output` - Remove empty tool outputs
- `step-metadata` - Trim step metadata

### Standard Tier (11 strategies, includes gentle)

- `dedup` - Deduplicate identical tool calls
- `error-purge` - Purge error inputs after N turns
- `reasoning-trim` - Trim extended thinking blocks
- `snapshot` - Remove old git snapshots
- `retry` - Remove retry metadata
- `patch` - Compress patch data

### Aggressive Tier (16 strategies, includes standard)

- `old-context-drop` - Drop oldest context
- `large-truncate` - Truncate oversized outputs
- `subtask-collapse` - Collapse subtask data
- `file-summarize` - Summarize file parts
- `thinning` - Aggressive message thinning

## License

MIT
