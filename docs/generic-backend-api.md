# Headroom Generic Backend API

## Design Principles

The Python CLI should be a **generic context compression backend** that:

1. **Is client-agnostic**: No knowledge of OpenCode, Claude, or any specific client
2. **Uses standard I/O**: Accepts JSON via stdin, outputs JSON to stdout
3. **Is stateless**: Each invocation is independent (no database coupling)
4. **Is composable**: Can be piped, scripted, and integrated anywhere

## Input Format

### Compress Request

```json
{
  "command": "compress",
  "prescription": "gentle" | "standard" | "aggressive",
  "session": {
    "id": "ses_abc123",
    "context_window": 200000,
    "current_usage": 150000
  },
  "messages": [
    {
      "id": "msg_001",
      "role": "user" | "assistant" | "system",
      "timestamp": 1719849600000,
      "parts": [
        {
          "id": "part_001",
          "type": "text",
          "content": "Hello world",
          "size_bytes": 11
        },
        {
          "id": "part_002",
          "type": "tool_call",
          "tool": "grep",
          "input": {"pattern": "foo"},
          "size_bytes": 128
        },
        {
          "id": "part_003",
          "type": "tool_result",
          "tool": "grep",
          "output": "match found",
          "size_bytes": 256
        }
      ]
    }
  ]
}
```

### Diagnose Request

```json
{
  "command": "diagnose",
  "messages": [ /* same format as compress */ ]
}
```

## Output Format

### Compress Response

```json
{
  "status": "success",
  "summary": {
    "original_size": 150000,
    "compressed_size": 95000,
    "savings_bytes": 55000,
    "savings_percent": 36.7
  },
  "actions": [
    {
      "action": "delete_part",
      "part_id": "part_002",
      "reason": "Stale tool call",
      "strategy": "stale-context",
      "savings_bytes": 128
    },
    {
      "action": "delete_part",
      "part_id": "part_003",
      "reason": "Orphaned tool result",
      "strategy": "error-purge",
      "savings_bytes": 256
    },
    {
      "action": "deduplicate",
      "part_ids": ["part_004", "part_005"],
      "keep_part_id": "part_004",
      "reason": "Identical content",
      "strategy": "dedup",
      "savings_bytes": 512
    }
  ]
}
```

### Diagnose Response

```json
{
  "status": "success",
  "bloat_sources": [
    {
      "category": "stale_tool_calls",
      "count": 12,
      "size_bytes": 4096,
      "percent": 15.2
    },
    {
      "category": "duplicate_content",
      "count": 5,
      "size_bytes": 2048,
      "percent": 7.6
    },
    {
      "category": "error_messages",
      "count": 3,
      "size_bytes": 1024,
      "percent": 3.8
    }
  ],
  "recommendations": [
    "Apply 'gentle' prescription to remove stale tool calls",
    "Consider 'standard' for duplicate content cleanup"
  ]
}
```

### Error Response

```json
{
  "status": "error",
  "error": "Invalid message format",
  "details": "Missing required field: messages[0].id"
}
```

## Usage Examples

### Compress Session

```bash
cat session.json | headroom-cli compress --rx gentle
```

### Diagnose Bloat

```bash
cat session.json | headroom-cli diagnose | jq '.bloat_sources'
```

### Integration with TypeScript Plugin

```typescript
import { spawn } from 'child_process';

const cli = spawn('headroom-cli', ['compress', '--rx', 'gentle']);

cli.stdin.write(JSON.stringify({
  command: 'compress',
  prescription: 'gentle',
  session: { /* ... */ },
  messages: [ /* ... */ ]
}));
cli.stdin.end();

let output = '';
cli.stdout.on('data', (data) => output += data);
cli.stdout.on('end', () => {
  const result = JSON.parse(output);
  console.log(`Saved ${result.summary.savings_bytes} bytes`);
});
```

## Migration Path

1. **Phase 1**: Implement generic stdin/stdout API (this design)
2. **Phase 2**: Move OpenCode database logic to `headroom-cli-opencode` adapter package
3. **Phase 3**: Update TypeScript plugin to use JSON pipe instead of database

## Backward Compatibility

Keep existing `--db` flag as a convenience wrapper:

```bash
# Old way (OpenCode-specific)
headroom-cli --db ~/.local/share/opencode/opencode.db list

# New way (generic)
headroom-cli-opencode export-session ses_abc | headroom-cli diagnose
```

The `headroom-cli-opencode` adapter would handle database-to-JSON conversion.
