import type { Part } from '@opencode-ai/sdk';
import type { HeadroomConfig, SessionState, Logger } from '../types.ts';

function formatStatus(state: SessionState): string {
  const lines: string[] = [];

  lines.push('## Headroom Context Pruning Status\n');
  lines.push(`Session: ${state.sessionId ?? 'none'}`);
  lines.push(`Turn: ${state.turnCount}`);
  lines.push(`Fetches: ${state.fetchCount}`);
  lines.push(`Total Bytes Saved: ${state.totalBytesSaved.toLocaleString()} bytes`);
  lines.push('');

  if (state.compressionBlocks.length > 0) {
    lines.push(`### Compression Blocks (${state.compressionBlocks.length})\n`);
    for (const block of state.compressionBlocks) {
      const saved = block.originalByteSize - block.compressedByteSize;
      lines.push(
        `- **${block.id}**: ${block.messageCount} messages, ${saved.toLocaleString()} bytes saved`
      );
    }
    lines.push('');
  }

  if (state.prunedPartIds.size > 0) {
    lines.push(`Pruned parts: ${state.prunedPartIds.size}`);
  }

  if (state.toolCache.size > 0) {
    lines.push(`Cached tools: ${state.toolCache.size}`);
  }

  return lines.join('\n');
}

export function createCommandHandler(config: HeadroomConfig, state: SessionState, logger: Logger) {
  return async (
    input: { command: string; sessionID: string; arguments: string },
    output: { parts: Part[] }
  ) => {
    const now = Date.now();
    const msgId = `headroom-cmd-${now}`;

    if (input.command === 'headroom') {
      const status = formatStatus(state);
      output.parts.push({
        id: `${msgId}-part`,
        sessionID: input.sessionID,
        messageID: msgId,
        type: 'text',
        text: status
      });
      logger.debug('Headroom status command executed');
    }

    if (input.command === 'headroom-compress') {
      state.pendingManualCompress = true;
      output.parts.push({
        id: `${msgId}-part`,
        sessionID: input.sessionID,
        messageID: msgId,
        type: 'text',
        text: '✓ Manual compression flag set. Compression will be applied on next request.'
      });
      logger.info('Manual compression triggered');
    }
  };
}
