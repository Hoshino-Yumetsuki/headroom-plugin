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
- **No strategy code**: All compression logic lives in headroom SDK

### 2. `opencode-plugin` (TypeScript)

**OpenCode adapter** - converts OpenCode's internal format to/from Anthropic format.

- Converts `MessageWithParts` → Anthropic messages
- Calls Python CLI via subprocess
- Converts compressed messages back to `MessageWithParts`
- Zero compression logic - pure format translation

## How It Works

The plugin communicates with the Python CLI via **stdin/stdout**:

1. TypeScript serializes messages to JSON
2. Sends via stdin to `headroom-plugin-cli`
3. Python CLI compresses and returns via stdout
4. TypeScript parses response and updates messages

**Key improvements for Windows compatibility:**

- Binary buffer writing (no text mode encoding issues)
- Spawns without shell (avoids PowerShell interference)
- UTF-8 explicit encoding on both sides

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

Create `.opencode/headroom.jsonc` in your project or `~/.config/opencode/headroom.jsonc` globally:

```jsonc
{
  "enabled": true,
  "cli": {
    // CLI path (default: "headroom-plugin-cli" - assumes it's in PATH)
    "path": "headroom-plugin-cli",

    // Compression level: "gentle" | "standard" | "aggressive"
    // - gentle: target_ratio=0.7, protect_recent=3 messages
    // - standard: target_ratio=0.5, protect_recent=2 messages
    // - aggressive: target_ratio=0.3, protect_recent=1 message, compresses user messages
    "prescription": "gentle"
  },
  "log": {
    "debug": false, // Enable detailed debug logs
    "info": true, // Enable info logs
    "path": "~/.config/opencode/logs/headroom"
  }
}
```

Project config at `.opencode/headroom.jsonc` overrides global settings.

## Troubleshooting

### Check logs

Logs are written to `~/.config/opencode/logs/headroom/` by default.

Enable debug logging in your config:

```jsonc
{
  "log": {
    "debug": true,
    "info": true
  }
}
```

### Test Python CLI directly

Test with stdin mode:

```bash
echo '{"messages":[{"role":"user","content":"Hello"}],"prescription":"gentle","model":"claude-sonnet-4","context_window":200000}' | headroom-plugin-cli
```

Expected output:

```json
{
  "status": "success",
  "messages": [...],
  "tokens_before": 9,
  "tokens_after": 9,
  "tokens_saved": 0,
  "compression_ratio": 0.0
}
```

### Common Issues

**"CLI exited with code 1"**

- Check that `headroom-plugin-cli` is installed: `which headroom-plugin-cli` (Linux/Mac) or `Get-Command headroom-plugin-cli` (Windows)
- Verify it's in PATH and executable
- Re-install if needed: `uv tool install headroom-plugin-cli@git+... --force`

**"Magika/ONNX detector is unsafe"**
This warning is harmless. It means the Python backend is using a pure-Python fallback for content detection. You can ignore it or set `HEADROOM_DETECT_BACKEND=rust` if you have the Rust backend installed.

### Verify format conversion

The TypeScript plugin logs conversion details:

```
[Converter] Converting to Anthropic format { messageCount: 10 }
[Converter] Converted message { messageId: 'xxx', role: 'user', partCount: 3, blockCount: 2 }
[CLI] Request written to CLI stdin { bytes: 12345 }
[CLI] Response parsed { status: 'success' }
[Converter] Converting from Anthropic format { anthropicCount: 6, originalCount: 8 }
```

## Development

### Build from source

```bash
# Python CLI
cd packages/headroom-plugin-cli
uv tool install --force --editable .

# TypeScript plugin
cd packages/opencode-plugin
npm install
npm run build
```

## License

MIT
