# OpenCode Headroom Plugin

A context-aware pruning and compression plugin for OpenCode that intelligently manages conversation context to prevent token budget overflow.

## Features

### 🎯 Smart Context Management

- **Intelligent Nudges**: Soft and strong nudges when context grows, with priority guidance
- **Range-Based Compression**: Compress message ranges while preserving semantics
- **Automatic Pruning**: Remove redundant, stale, and error-prone parts
- **Session Persistence**: Track compression blocks and pruned parts across sessions

### 🔧 Pruning Strategies

1. **Deduplication**: Removes duplicate tool calls with identical inputs
2. **Error Purge**: Cleans up error inputs after N turns
3. **Stale Context**: Removes superseded file reads (keeps only the latest)

### 📊 Priority-Based Guidance

The plugin classifies messages into priority tiers:

- **High**: User messages, protected tools
- **Medium**: Tool calls with errors
- **Low**: Successful tool calls (compress-first candidates)

## Installation

```bash
yarn add @q78kg/opencode-headroom
```

## Configuration

Create `.opencode/headroom.jsonc` in your project:

```jsonc
{
  "enabled": true,
  "compress": {
    "mode": "range",
    "permission": "allow",
    "maxContextLimit": 180000,
    "minContextLimit": 120000,
    "nudgeFrequency": 3,
    "iterationNudgeThreshold": 10,
    "protectedTools": ["read", "write", "edit"],
    "protectUserMessages": true
  },
  "strategies": {
    "deduplication": { "enabled": true },
    "purgeErrors": { "enabled": true, "turns": 5 },
    "staleContext": { "enabled": true }
  },
  "cli": {
    "path": "headroom",
    "prescription": "standard"
  },
  "protectedFilePatterns": ["*.md", "*.json"]
}
```

### Configuration Options

| Option                             | Type                             | Default                     | Description                                     |
| ---------------------------------- | -------------------------------- | --------------------------- | ----------------------------------------------- |
| `enabled`                          | boolean                          | `true`                      | Enable/disable the plugin                       |
| `compress.mode`                    | `"range"` \| `"message"`         | `"range"`                   | Compression mode                                |
| `compress.permission`              | `"allow"` \| `"ask"` \| `"deny"` | `"allow"`                   | Permission for compression tool                 |
| `compress.maxContextLimit`         | number                           | `180000`                    | Token limit for strong nudges                   |
| `compress.minContextLimit`         | number                           | `120000`                    | Token limit for soft nudges                     |
| `compress.nudgeFrequency`          | number                           | `3`                         | How often to inject nudges (in fetches)         |
| `compress.iterationNudgeThreshold` | number                           | `10`                        | Turns without user input before iteration nudge |
| `compress.protectedTools`          | string[]                         | `["read", "write", "edit"]` | Tools to never prune                            |
| `compress.protectUserMessages`     | boolean                          | `true`                      | Never compress user messages                    |
| `strategies.deduplication.enabled` | boolean                          | `true`                      | Enable deduplication strategy                   |
| `strategies.purgeErrors.enabled`   | boolean                          | `true`                      | Enable error purging                            |
| `strategies.purgeErrors.turns`     | number                           | `5`                         | Turns before purging error inputs               |
| `strategies.staleContext.enabled`  | boolean                          | `true`                      | Enable stale context removal                    |

## Usage

### Compress Tool

The plugin provides a `compress` tool accessible to the agent:

```typescript
compress({
  startId: 'm0010', // Short ID from <headroom-id> tags
  endId: 'm0050',
  summary: 'Implemented authentication module with JWT tokens and refresh logic'
});
```

### Commands

```bash
# Check plugin status
/headroom

# Trigger manual compression
/headroom-compress
```

### Message ID Tags

The plugin injects `<headroom-id>m0042</headroom-id>` tags into messages for easy reference when compressing.

## How It Works

### 1. Message Transform Pipeline

On every message fetch:

1. Filter malformed messages
2. Check for session changes (resets state on new session)
3. Strip model-generated metadata
4. Assign short IDs (m0001, m0002, ...)
5. Run all enabled pruning strategies in parallel
6. Apply compression blocks (replace ranges with summaries)
7. Prune marked parts
8. Calculate priority map
9. Inject compression nudges if thresholds exceeded
10. Inject message ID tags

### 2. Compression Workflow

```
User: "I want to compress messages m0010 to m0050"
  ↓
Agent calls compress({ startId: "m0010", endId: "m0050", summary: "..." })
  ↓
Plugin creates compression block
  ↓
On next message fetch, the range is replaced with:
[Compressed 40 messages (45,210 → 1,530 bytes)]

<summary>
...
</summary>
```

### 3. Nudge Escalation

| Context Tokens      | Nudge Type | Action                                   |
| ------------------- | ---------- | ---------------------------------------- |
| < 120,000           | None       | Silent operation                         |
| 120,000 - 180,000   | Soft       | "Consider compressing" (on user message) |
| > 180,000           | Strong     | "Strongly recommend" + priority guidance |
| After 10 iterations | Iteration  | "Consider compressing the working phase" |

## Architecture

```
src/
├── compress/          # Compression state and tool
│   ├── index.ts       # Session state management
│   ├── state.ts       # State reset and helpers
│   ├── range.ts       # Range compression tool
│   └── types.ts       # Compression types
├── nudge/             # Context nudge system
│   ├── system.ts      # System prompt injection
│   └── inject.ts      # Nudge message builder
├── pruning/           # Pruning strategies
│   ├── registry.ts    # Strategy registration
│   ├── prune.ts       # Compression block application
│   ├── transform.ts   # Main transform pipeline
│   └── strategies/    # Individual strategies
│       ├── dedup.ts
│       ├── error-purge.ts
│       └── stale-context.ts
├── commands/          # CLI commands
│   └── handler.ts
├── config.ts          # Configuration loader
├── logger.ts          # Logging utility
├── message-ids.ts     # Short ID management
├── token-utils.ts     # Token estimation
├── types.ts           # Core types
├── hooks.ts           # Hook factories
└── index.ts           # Plugin entry point
```

## Development

```bash
# Install dependencies
yarn install

# Build
yarn build

# Type check
yarn tsc --noEmit

# Lint (optional - requires oxlint-tsgolint)
yarn lint
```

## License

MIT

## Contributing

Contributions welcome! Please ensure:

- TypeScript strict mode compliance
- All public APIs documented
- Hooks follow OpenCode plugin conventions
