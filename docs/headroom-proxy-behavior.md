# Headroom Reverse Proxy - Behavior Analysis

This document analyzes the behavior of the upstream headroom reverse proxy at https://github.com/headroomlabs-ai/headroom to inform plugin implementation decisions.

## Architecture Overview

The headroom proxy operates as a **transparent reverse proxy** that sits between LLM clients (Claude Code, Cursor, Codex, etc.) and LLM APIs (Anthropic, OpenAI, Bedrock, Vertex). It applies context compression optimizations while maintaining wire-level compatibility.

**Key Architecture Points:**
- **Dual Implementation**: Rust (headroom-proxy) + Python (headroom.proxy)
- **Deployment Model**: Rust proxy is the frontend (public-facing), Python handles compression
- **Local-First**: All processing happens locally; user data never leaves the machine
- **Reversible (CCR)**: Originals cached for retrieval on demand

---

## 1. Logging System

### 1.1 Rust Proxy Logging

**Format**: **Structured JSON** with consistent fields

```rust
// From main.rs:85-95
fn init_tracing(level: &str) {
    let filter = EnvFilter::try_new(level).unwrap_or_else(|_| EnvFilter::new("info"));
    let json_layer = tracing_subscriber::fmt::layer()
        .json()
        .with_current_span(false)
        .with_span_list(false);
    tracing_subscriber::registry()
        .with(filter)
        .with(json_layer)
        .try_init();
}
```

**Key Characteristics:**
- **Default Level**: `info` (configurable via `--log-level`)
- **Format**: Pure JSON (no text fallback)
- **No Span Tracking**: `with_current_span(false)` - cleaner logs for proxy patterns
- **No Rotation Built-In**: Rust proxy writes to stdout; rotation handled externally

**Sample Log Entries:**

```rust
// Startup
tracing::info!(
    listen = %config.listen,
    upstream = %config.upstream,
    upstream_timeout_s = config.upstream_timeout.as_secs(),
    max_body_bytes = config.max_body_bytes,
    "headroom-proxy starting"
);

// Request processing
tracing::debug!(
    event = "policy_selected",
    request_id = %request_id,
    auth_mode = auth_mode.as_str(),
    live_zone_only = policy.live_zone_only,
    "compression policy resolved"
);

// Errors
tracing::error!(
    event = "handler_error",
    handler = "chat_completions",
    error = %e,
    "failed to reconstruct request from buffered body"
);
```

**Standard Fields:**
- `event`: Event type identifier
- `request_id`: UUID for request tracking
- `path`, `method`, `status`: HTTP metadata
- `auth_mode`, `policy`: Compression decision context
- Metric fields: `bytes`, `tokens`, `ratio`, etc.

### 1.2 Python Proxy Logging

**Format**: Text with structured fields via `logging.basicConfig`

```python
# From server.py:444-447
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("headroom.proxy")
```

**Characteristics:**
- **Default Level**: `INFO`
- **Format**: `YYYY-MM-DD HH:MM:SS - logger.name - LEVEL - message`
- **Optional File Rotation**: Via `RotatingFileHandler` (configurable)

```python
# From helpers.py:999-1026
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    path,
    maxBytes=max_bytes,       # Default: 10MB
    backupCount=backup_count,  # Default: 3
    encoding="utf-8",
)
handler.setLevel(level)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
))
```

**Rotation Behavior:**
- Rotation triggers at `maxBytes` (default 10MB)
- Keeps `backupCount` backup files (default 3)
- Files named: `headroom.log`, `headroom.log.1`, `headroom.log.2`, etc.
- **No Compression**: Rotated files are NOT compressed by default

### 1.3 Timezone Handling

**CRITICAL FINDING**: Both implementations use **local system time** via default formatters:

**Rust:**
- `tracing_subscriber` with JSON output includes ISO 8601 timestamps
- **No explicit timezone conversion** - uses system local time
- Timestamps in JSON include fractional seconds

**Python:**
- `%(asctime)s` uses `time.localtime()` by default
- Format: `YYYY-MM-DD HH:MM:SS,mmm` (milliseconds)
- **No timezone identifier in output**

**Implications for Plugin:**
- **Match local time behavior** for consistency
- Consider adding explicit timezone markers if users need UTC
- Timestamp parsing should handle both formats

---

## 2. Request/Response Processing

### 2.1 HTTP Request Flow

```
Client Request
    ↓
┌───────────────────────────────────────┐
│ 1. Connection Handler                 │
│    - Extract headers                  │
│    - Generate request_id (UUID v4)    │
│    - Log inbound request              │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 2. Path Classification                │
│    - /v1/messages (Anthropic)         │
│    - /v1/chat/completions (OpenAI)    │
│    - Bedrock/Vertex endpoints         │
│    - Passthrough (other)              │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 3. Body Buffering Decision            │
│    - Compressible paths → buffer      │
│    - Check max_body_bytes limit       │
│    - Oversized → passthrough          │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 4. Compression Gate                   │
│    - Auth mode check                  │
│    - Policy selection                 │
│    - Skip rules (n>1, etc.)           │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 5. Header Transformation              │
│    - Strip x-headroom-* (default)     │
│    - Add Forwarded-For                │
│    - Rewrite Host (configurable)      │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 6. Upstream Forward                   │
│    - HTTP/SSE/WebSocket               │
│    - Timeout enforcement              │
│    - Response streaming               │
└───────────────────────────────────────┘
```

### 2.2 Compression Pipeline

```rust
// From proxy.rs compression gate
match endpoint {
    CompressibleEndpoint::Anthropic => {
        // Live-zone compression (latest user message + tool outputs)
        compress_anthropic_request(body, policy, request_id)
    }
    CompressibleEndpoint::OpenAIChat => {
        // Skip if n > 1 (non-deterministic)
        if should_skip_n_greater_than_one(&body) {
            return Passthrough;
        }
        compress_openai_chat_request(body, policy, request_id)
    }
}
```

**Compression Modes** (from `config.rs:8-31`):
- `Off`: Byte-equal passthrough (default in Phase A)
- `LiveZone`: Compress latest user message + tool outputs

**Skip Conditions:**
- **OpenAI**: `n > 1` (multiple completions)
- **Anthropic**: No automatic skips
- **All**: Body exceeds `compression_max_body_bytes`

### 2.3 SSE (Server-Sent Events) Handling

**Critical Feature**: Zero-copy, byte-level SSE framing

```rust
// From sse/framing.rs:84-92
pub struct SseFramer {
    buf: BytesMut,  // Accumulator for incomplete events
    done_seen: bool,
}

// Events terminate on \n\n
// Lines starting with : are comments (dropped)
// data: [DONE] is stream-end sentinel (OpenAI)
```

**Why Byte-Level?**
> "The Python proxy decoded each TCP chunk to UTF-8 with errors='ignore', 
> which silently lost bytes whenever a multi-byte codepoint (any emoji, 
> any non-ASCII character) straddled a chunk boundary. Production telemetry 
> logged 1946 parse failures over 9 days from this single quirk."

**Plugin Implication**: Our TypeScript plugin must handle UTF-8 correctly across chunk boundaries.

### 2.4 Streaming Response Processing

```rust
// From proxy.rs - ChunkState machine
enum ChunkState {
    Head { .. },            // Accumulating for telemetry
    PassthroughBody { .. }, // Direct relay
    PassthroughDone,        // Stream complete
}
```

**Telemetry Collection:**
- Buffers response chunks up to a limit
- Extracts usage metadata (`input_tokens`, `output_tokens`)
- Emits Prometheus metrics
- Logs compression ratio

**Streaming Passthrough:**
- After telemetry limit, switches to zero-copy relay
- Preserves SSE framing byte-for-byte
- No buffering overhead after limit

---

## 3. Observability & Metrics

### 3.1 Prometheus Metrics

**Metric Types** (from `observability/proxy_metrics.rs`):

```rust
// Rate limit gauges
proxy_rate_limit_remaining_requests{provider}
proxy_rate_limit_remaining_tokens{provider}
proxy_rate_limit_remaining_input_tokens{provider}
proxy_rate_limit_remaining_output_tokens{provider}

// Passthrough safety alarm
proxy_passthrough_bytes_modified_total{path}

// Response tracking
proxy_response_status_count_total{provider, status}
proxy_service_tier_count_total{tier}

// Compression metrics
proxy_compression_ratio{endpoint, auth_mode}
proxy_cache_hit_rate{provider}
```

**Force-Zero Contract** (H3/H4 fix):
> "The `gather()` semantics in prometheus v0.13.4 omit empty MetricVec 
> families from scrapes. We force-touch each counter/gauge with a sentinel 
> label on boot so HELP/TYPE appear even when the metric is zero."

### 3.2 Audit Logging

```python
# From audit.py:19, 57-59
audit_logger = logging.getLogger("headroom.audit")

def emit_audit_event(event: dict) -> None:
    try:
        audit_logger.info(json.dumps(event, ensure_ascii=False, default=str))
    except Exception:
        audit_logger.warning("audit event emission failed", exc_info=True)
```

**Audit Events**: Separate logger for compliance/security events

### 3.3 Request ID Tracking

```rust
// From proxy.rs - request_id generation
let request_id = uuid::Uuid::new_v4().to_string();

// Logged in every relevant event
tracing::info!(
    request_id = %request_id,
    // ... other fields
);
```

**Propagation:**
- Generated at proxy entry
- Passed to compression pipeline
- Logged in all related events
- NOT forwarded to upstream (internal only)

---

## 4. Configuration & Behavior Flags

### 4.1 Key Configuration Options

```rust
// From config.rs:CliArgs
pub struct CliArgs {
    #[arg(long, default_value = "0.0.0.0:8787")]
    pub listen: SocketAddr,
    
    #[arg(long, default_value = "http://localhost:8000")]
    pub upstream: String,
    
    #[arg(long, default_value = "60s")]
    pub upstream_timeout: Duration,
    
    #[arg(long, default_value = "10s")]
    pub upstream_connect_timeout: Duration,
    
    #[arg(long, default_value = "128MB")]
    pub max_body_bytes: u64,
    
    #[arg(long, default_value = "info")]
    pub log_level: String,
    
    #[arg(long, default_value_t = true)]
    pub rewrite_host: bool,
    
    #[arg(long, env = "HEADROOM_PROXY_COMPRESSION", default_value_t = false)]
    pub compression: bool,
    
    #[arg(long, default_value = "enabled")]
    pub strip_internal_headers: StripInternalHeaders,
}
```

### 4.2 Header Stripping Policy

```rust
// From config.rs:48-72
pub enum StripInternalHeaders {
    Enabled,   // Default - drop x-headroom-* headers
    Disabled,  // Diagnostic only - forwards to upstream
}
```

**Stripping Behavior** (from `proxy.rs:479-513`):
```rust
let strip_internal = state.config.strip_internal_headers.is_enabled();
let pre_strip_internal_count = req.headers()
    .iter()
    .filter(|(name, _)| is_internal_header(name))
    .count();

if strip_internal && pre_strip_internal_count > 0 {
    tracing::info!(
        event = "outbound_headers",
        stripped_count = pre_strip_internal_count,
        request_id = %request_id,
        "stripped internal x-headroom-* headers from upstream-bound request"
    );
}
```

**Internal Header Pattern**: Any header starting with `x-headroom-`

---

## 5. Error Handling & Safety

### 5.1 Rust Core Deployment Check

**Critical Startup Validation** (from `server.py:468-536`):

```python
def _check_rust_core() -> tuple[str, str | None]:
    """Verify Rust extension is loadable at startup."""
    require = os.environ.get("HEADROOM_REQUIRE_RUST_CORE", "true") != "false"
    
    try:
        from headroom._core import hello as _rust_hello
        marker = _rust_hello()
    except Exception as exc:
        if not require:
            logger.warning("rust_core_disabled, mode=python_only_degraded")
            return ("disabled", reason)
        
        # Fail loud with exit code 78 (EX_CONFIG)
        logger.error("rust_core_missing, action=exit_78")
        sys.exit(78)
    
    if marker != "headroom-core":
        # Marker mismatch = stale/mis-linked .so
        sys.exit(78)
    
    logger.info("rust_core_loaded")
    return ("loaded", None)
```

**Exit Code 78**: sysexits.h `EX_CONFIG` - tells process supervisors (systemd, k8s) this is a config failure, not a crash.

### 5.2 Passthrough Safety Alarm

```rust
// From observability/proxy_metrics.rs:55-67
pub fn record_passthrough_bytes_modified(path: &str, bytes: u64, request_id: &str) {
    passthrough_bytes_modified_counter(registry())
        .with_label_values(&[path])
        .inc_by(bytes);
    
    tracing::warn!(
        event = "passthrough_bytes_modified",
        path = %path,
        bytes = bytes,
        request_id = %request_id,
        "passthrough path modified bytes; this is the cache-safety alarm condition"
    );
}
```

**Purpose**: Detect when a path marked as "passthrough" (should be byte-equal) has been modified. This is the **cache-safety alarm** - critical for debugging prompt cache busts.

### 5.3 Body Size Limits

```rust
// From proxy.rs:605-616
let body_bytes = match body_bytes_result {
    Ok(bytes) if bytes.len() <= max => bytes,
    Ok(bytes) => {
        tracing::info!(
            event = "buffering_limit_exceeded",
            body_bytes = bytes.len(),
            max_bytes = max,
            "request body exceeds compression buffer limit"
        );
        return Ok(forward_passthrough_request(...));
    }
    Err(e) => { ... }
};
```

**Behavior**: Requests exceeding `compression_max_body_bytes` bypass compression entirely and are forwarded unchanged.

---

## 6. Key Differences from OpenCode Plugin

### 6.1 Scope & Responsibility

| Aspect | Headroom Proxy | OpenCode Plugin |
|--------|----------------|-----------------|
| **Deployment** | Standalone network proxy | In-process plugin |
| **Data Flow** | HTTP/SSE interception | SDK message hooks |
| **Compression** | Content-aware (JSON, code, text) | Message/part-level |
| **State** | Stateless per-request | Session-scoped state tracking |
| **Telemetry** | Prometheus + structured logs | In-memory session state |
| **Reversibility** | CCR cache (SQLite/Redis) | Memory only |

### 6.2 Compression Strategy

**Headroom Proxy:**
- **Live-zone only**: Compresses latest user message + recent tool outputs
- **Content-aware**: Routes JSON → SmartCrusher, Code → AST, Text → Kompress-v2
- **Provider-specific**: Different logic for Anthropic vs OpenAI
- **Caching**: CCR (Content-Controlled Retrieval) stores originals

**OpenCode Plugin:**
- **Message-range compression**: User specifies startId/endId
- **LLM-generated summaries**: Calls LLM to summarize message ranges
- **Tool deduplication**: Caches identical tool results
- **Pruning strategies**: Dedupe, purge errors, stale context removal

### 6.3 Logging Philosophy

**Headroom Proxy:**
- **Structured first**: JSON logs from Rust, parseable text from Python
- **Metrics-driven**: Prometheus for dashboards, logs for debugging
- **Request-scoped**: Every log tied to request_id

**OpenCode Plugin (Current):**
- **Simple console logs**: `console.log` with basic formatting
- **No structured output**: Free-form text messages
- **Limited context**: No request correlation

**Recommendation for Plugin:**
- Adopt structured logging similar to headroom
- Add session_id correlation (equivalent to request_id)
- Consider JSON output option for production use

---

## 7. Recommendations for Plugin Implementation

### 7.1 Logging Improvements

1. **Adopt Structured Logging:**
   ```typescript
   logger.info({
     event: 'compression_complete',
     sessionId: state.sessionId,
     blockId: block.id,
     originalBytes: block.originalByteSize,
     compressedBytes: block.compressedByteSize,
     ratio: (block.originalByteSize / block.compressedByteSize).toFixed(2),
     messageCount: block.messageCount,
   });
   ```

2. **Add Timezone Clarity:**
   ```typescript
   // Option 1: Use ISO 8601 with timezone
   const timestamp = new Date().toISOString(); // "2026-07-01T12:34:56.789Z"
   
   // Option 2: Explicit local time with marker
   const localTime = new Date().toLocaleString('en-US', {
     timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
     hour12: false,
   });
   const tzMarker = Intl.DateTimeFormat().resolvedOptions().timeZone;
   logger.info(`${localTime} [${tzMarker}] - event details`);
   ```

3. **Request/Session Correlation:**
   - Add `sessionId` to every log entry
   - Include `messageId` when operating on specific messages
   - Track `compressionBlockId` for compression operations

### 7.2 Configuration Alignment

Consider adding headroom-style configuration options:

```typescript
interface HeadroomConfig {
  // ... existing config
  
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error';
    format: 'text' | 'json';
    includeTimezone: boolean;
    requestIdInLogs: boolean; // Use sessionId
  };
  
  compression: {
    maxBodyBytes: number;  // Like headroom's max_body_bytes
    timeoutSeconds: number; // Compression timeout
  };
  
  telemetry: {
    enableMetrics: boolean;
    enableAuditLog: boolean;
  };
}
```

### 7.3 Safety Mechanisms

Adopt headroom's safety patterns:

1. **Byte-Level Verification:**
   ```typescript
   // Track modifications to parts marked as "protected"
   function verifyUnmodified(original: Part, current: Part): boolean {
     return original.contentHash === current.contentHash;
   }
   ```

2. **Size Limits:**
   ```typescript
   if (messageByteSize > config.compress.maxBodyBytes) {
     logger.info({
       event: 'compression_skipped',
       reason: 'size_limit_exceeded',
       messageBytes: messageByteSize,
       limit: config.compress.maxBodyBytes,
     });
     return SkipCompression;
   }
   ```

3. **Timeout Protection:**
   ```typescript
   const compressionPromise = compressMessages(messages);
   const timeoutPromise = new Promise((_, reject) =>
     setTimeout(() => reject(new Error('compression_timeout')), 
                config.compress.timeoutSeconds * 1000)
   );
   
   try {
     await Promise.race([compressionPromise, timeoutPromise]);
   } catch (err) {
     logger.warn({ event: 'compression_timeout', sessionId });
     return SkipCompression;
   }
   ```

### 7.4 Observability Additions

1. **Compression Metrics:**
   ```typescript
   interface CompressionMetrics {
     totalCompressionsAttempted: number;
     totalCompressionsSucceeded: number;
     totalCompressionsFailed: number;
     totalOriginalBytes: number;
     totalCompressedBytes: number;
     averageCompressionRatio: number;
     averageCompressionTimeMs: number;
   }
   ```

2. **Session State Snapshot:**
   ```typescript
   logger.debug({
     event: 'session_state_snapshot',
     sessionId: state.sessionId,
     compressionBlockCount: state.compressionBlocks.length,
     prunedPartCount: state.prunedPartIds.size,
     totalBytesSaved: state.totalBytesSaved,
     turnCount: state.turnCount,
   });
   ```

3. **Error Context:**
   ```typescript
   logger.error({
     event: 'compression_error',
     sessionId: state.sessionId,
     messageId: message.id,
     error: err.message,
     stack: err.stack,
     context: {
       messageCount: messages.length,
       totalBytes: messages.reduce((sum, m) => sum + estimateSize(m), 0),
     },
   });
   ```

---

## 8. Summary of Key Behaviors

### Logging
- **Rust**: Structured JSON, `info` level default, local time, no rotation
- **Python**: Text format with rotation option, `INFO` level default, local time
- **Fields**: Consistent event/request_id/path/status pattern

### Request Processing
- **Buffering**: Compressible paths buffer bodies up to max_body_bytes
- **Path Classification**: Per-provider logic (Anthropic, OpenAI, Bedrock, Vertex)
- **Header Transformation**: Strips `x-headroom-*` by default, rewrites Host
- **Streaming**: Zero-copy SSE framing, byte-level UTF-8 handling

### Safety & Observability
- **Passthrough Alarm**: Detects unintended modifications
- **Rust Core Check**: Fails loud at startup if extension missing
- **Metrics**: Prometheus counters/gauges for compression, rate limits, status codes
- **Request Correlation**: UUID request_id in all logs

### Configuration
- **Compression**: Off by default, opt-in via `--compression` flag
- **Size Limits**: max_body_bytes (default 128MB), compression_max_body_bytes
- **Timeouts**: upstream_timeout (60s), upstream_connect_timeout (10s)
- **Log Level**: Configurable via `--log-level`, default `info`

---

## References

- [Headroom Repository](https://github.com/headroomlabs-ai/headroom)
- [Rust Proxy Source](https://github.com/headroomlabs-ai/headroom/tree/main/crates/headroom-proxy)
- [Python Proxy Source](https://github.com/headroomlabs-ai/headroom/tree/main/headroom/proxy)
- [Realignment Docs](https://github.com/headroomlabs-ai/headroom/tree/main/REALIGNMENT)
