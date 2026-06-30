# @q78kg/opencode-headroom

Real-time context pruning for OpenCode sessions — inspired by [cozempic](https://github.com/Ruya-AI/cozempic) and aligned with [headroom](https://github.com/headroomlabs-ai/headroom) reverse proxy behavior.

## Design Principles

This plugin follows the **transparency principle** of the headroom reverse proxy:

- **No metadata injection**: The plugin does not inject any visible content into messages sent to the LLM
- **Internal tracking only**: Message IDs and compression metadata are tracked internally
- **Non-invasive pruning**: Context cleanup happens transparently without modifying user or model messages
- **JSON structured logging**: Machine-readable logs with local timezone timestamps
- **Automatic log rotation**: Date-based log files (YYYY-MM-DD.log) with automatic gzip compression

## Architecture

This plugin uses **headroom SDK** for intelligent context compression. The architecture is clean and simple:

### 1. `headroom-plugin-cli` (Python)

**Generic compression backend** - client-agnostic, powered by [headroom SDK](https://headroomlabs-ai.github.io/headroom/).

- **Input**: Anthropic/OpenAI format messages (JSON via stdin)
- **Output**: Compressed messages with metrics (JSON via stdout)  
- **Compression**: Delegated to headroom SDK's battle-tested algorithms
- **No strategy code**: All compression logic lives in headroom

### 2. `opencode-plugin` (TypeScript)

**OpenCode adapter** - converts OpenCode's internal format to/from Anthropic format.

- Converts `MessageWithParts` → Anthropic messages
- Calls Python CLI
- Converts compressed messages back to `MessageWithParts`
- Zero compression logic - pure format translation

## Installation

### Python CLI

Using `uv` (recommended):

```bash
uv tool install headroom-plugin-cli@git+https://github.com/Hoshino-Yumetsuki/headroom-plugin.git#subdirectory=packages/headroom-plugin-cli --upgrade
```

Using `pip`:

```bash
pip install headroom-plugin-cli@git+https://github.com/Hoshino-Yumetsuki/headroom-plugin.git#subdirectory=packages/headroom-plugin-cli --upgrade
```

### OpenCode Plugin

```bash
opencode plugin add @q78kg/opencode-headroom
```

## Configuration

Global config at `~/.config/opencode/headroom.jsonc`:

```jsonc
{
  "enabled": true,
  "compress": {
    "mode": "range",
    "maxContextLimit": 100000,
    "minContextLimit": 50000,
    "nudgeFrequency": 5,
    "protectedTools": ["task", "skill", "todowrite"],
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

Project config at `.opencode/headroom.jsonc` overrides global settings.

## How It Works

1. OpenCode plugin hooks into message transform
2. Converts messages to generic JSON format
3. Calls Python CLI via stdin/stdout
4. Applies compression actions returned from CLI
5. Logs all operations with structured JSON

## License

MIT
