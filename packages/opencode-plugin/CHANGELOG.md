# Changelog

All notable changes to the OpenCode Headroom Plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-30

### Added

- **Core Plugin Infrastructure**
  - Message transform pipeline with filtering, ID assignment, and pruning
  - Session state management with automatic reset on session change
  - Configuration loader with global and project-level overrides
  - Logger utility for debug/info/warn/error levels

- **Compression System**
  - Range-based compression tool for agent use
  - Compression block storage and application
  - Short message IDs (m0001, m0002, ...) with `<headroom-id>` tags
  - Byte size calculation and token estimation

- **Pruning Strategies**
  - **Deduplication**: Remove duplicate tool calls with identical inputs
  - **Error Purge**: Clean up error tool inputs after N turns
  - **Stale Context**: Remove superseded file reads (keep only latest)
  - Strategy registry for extensibility

- **Nudge System**
  - Soft nudges when context approaches limit (120k tokens)
  - Strong nudges with priority guidance when exceeding limit (180k tokens)
  - Iteration nudges after long agent loops without user input
  - System prompt augmentation with compression guidance

- **Commands**
  - `/headroom` - Show plugin status with compression blocks and stats
  - `/headroom-compress` - Trigger manual compression flag

- **Priority Classification**
  - High: User messages, protected tools
  - Medium: Tool calls with errors
  - Low: Successful tool calls (compress-first candidates)

### Technical

- Full TypeScript type safety with strict mode
- Uses OpenCode Plugin SDK v1.17.11
- Rolldown bundler with optimized output
- Modular architecture with clear separation of concerns

[0.1.0]: https://github.com/headroom-plugin/opencode-plugin/releases/tag/v0.1.0
