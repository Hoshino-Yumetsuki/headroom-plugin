# Headroom Plugin

Real-time context pruning for OpenCode sessions — inspired by [cozempic](https://github.com/Ruya-AI/cozempic) and powered by headroom compression algorithms.

## Architecture

This monorepo contains two packages:

### 1. `headroom-plugin-cli` (Python)

Backend CLI tool for OpenCode session pruning. Uses stdlib-only (zero dependencies) for maximum portability.

**Features:**

- 16 pruning strategies across 3 tiers (gentle/standard/aggressive)
- SQLite-based OpenCode session reader
- Guard daemon for automatic monitoring
- Dry-run by default with explicit `--execute` flag
- Cross-platform (Windows/Linux/macOS)

**Commands:**

```bash
headroom-plugin-cli list                    # List all sessions
headroom-plugin-cli diagnose <session>      # Analyze bloat sources
headroom-plugin-cli treat <session> -rx gentle --execute  # Apply gentle pruning
headroom-plugin-cli strategy <name> <session> --execute   # Run single strategy
headroom-plugin-cli guard --daemon -rx standard           # Background monitoring
headroom-plugin-cli doctor                  # Health check
headroom-plugin-cli formulary               # Show all strategies
```

### Installation Guide

#### Installing the Python CLI (`headroom-plugin-cli`)

To install the Python package directly from a git repository URL (e.g., GitHub), you can use `pip` or `uv`. The format is `package_name@git+url`.

Using `uv` (recommended):

```bash
uv pip install headroom-plugin-cli@git+https://github.com/your-org/headroom-plugin.git#subdirectory=packages/headroom-plugin-cli
```

Using standard `pip`:

```bash
pip install headroom-plugin-cli@git+https://github.com/your-org/headroom-plugin.git#subdirectory=packages/headroom-plugin-cli
```

_(Note: Because this is a monorepo, you must specify the `#subdirectory=` fragment to point to the Python package folder.)_

#### Installing the OpenCode Plugin (`opencode-plugin`)

To install the OpenCode plugin (npm package) directly from a git repository URL:

Using the OpenCode CLI:

```bash
opencode plugin add git+https://github.com/your-org/headroom-plugin.git#workspace=opencode-headroom
```

_(Note: Replace `your-org/headroom-plugin` with the actual repository URL. The `#workspace=` fragment is required for monorepos to specify which package to install from the repo)._

If you are developing locally:

```bash
opencode plugin add ./packages/opencode-plugin
```

**Configuration:**

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
  }
}
```

Project config at `.opencode/headroom.jsonc` (overrides global).

## Development

### Setup

```bash
# Install dependencies
yarn install

# Build all packages
yarn build

# Lint
yarn lint

# Format
yarn format
```

### Toolchain

- **Yarn workspaces** - Monorepo management
- **oxlint + oxfmt** - Fast TypeScript linting and formatting
- **rolldown** - Fast ESM bundler for TypeScript
- **uv** - Python environment management (for headroom-cli)
- **TypeScript 6** - Type-safe plugin development

### Package Structure

```
headroom-plugin/
├── packages/
│   ├── headroom-plugin-cli/          # Python CLI backend
│   │   ├── pyproject.toml
│   │   └── src/headroom_cli/
│   │       ├── cli.py         # argparse entry point
│   │       ├── types.py       # Domain dataclasses
│   │       ├── registry.py    # Strategy decorator pattern
│   │       ├── session.py     # OpenCode SQLite reader
│   │       ├── diagnosis.py   # Bloat analysis
│   │       ├── executor.py    # Action execution
│   │       ├── guard.py       # Daemon mode
│   │       └── strategies/    # 16 pruning strategies
│   │           ├── gentle.py
│   │           ├── standard.py
│   │           └── aggressive.py
│   │
│   └── opencode-plugin/       # TypeScript plugin
│       ├── package.json
│       ├── rolldown.config.ts
│       └── src/
│           ├── index.ts       # Plugin entry point
│           ├── hooks.ts       # Hook factories
│           ├── config.ts      # Three-layer config
│           ├── compress/      # Range compression tool
│           ├── pruning/       # Pruning strategies
│           ├── nudge/         # Nudge system
│           ├── bridge/        # Python CLI bridge
│           └── commands/      # Slash command handlers
│
├── package.json               # Root workspace config
├── .oxlintrc.json            # Lint rules
├── .oxfmtrc.json             # Format rules
├── .editorconfig             # Editor config
└── .gitattributes            # Git line ending rules
```

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

## References

- [cozempic](https://github.com/Ruya-AI/cozempic) - Context cleaning CLI for Claude Code
- [opencode-dynamic-context-pruning](https://github.com/Opencode-DCP/opencode-dynamic-context-pruning) - Real-time context pruning for OpenCode
- [headroom](https://github.com/headroomlabs-ai/headroom) - Context compression proxy for AI agents
