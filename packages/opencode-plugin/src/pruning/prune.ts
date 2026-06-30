import type { MessageWithParts, SessionState, Logger } from '../types.ts';

export function applyCompressionBlocks(
  messages: MessageWithParts[],
  state: SessionState,
  logger: Logger
): void {
  const sortedBlocks = [...state.compressionBlocks].sort((a, b) => {
    const aStart = messages.findIndex((m) => m.info.id === a.startMessageId);
    const bStart = messages.findIndex((m) => m.info.id === b.startMessageId);
    return aStart - bStart;
  });

  for (const block of sortedBlocks) {
    const startIndex = messages.findIndex((m) => m.info.id === block.startMessageId);
    const endIndex = messages.findIndex((m) => m.info.id === block.endMessageId);

    if (startIndex === -1 || endIndex === -1) {
      logger.warn(`Compression block ${block.id} references missing messages`);
      continue;
    }

    const msgId = `compressed-${block.id}`;
    const text = `[Compressed ${block.messageCount} messages (${block.originalByteSize.toLocaleString()} → ${block.compressedByteSize.toLocaleString()} bytes)]\n\n${block.summary}`;

    const compressionMessage: MessageWithParts = {
      info: {
        id: msgId,
        sessionID: 'headroom',
        role: 'assistant',
        time: {
          created: block.createdAt
        },
        parentID: 'system',
        modelID: 'headroom',
        providerID: 'headroom',
        mode: 'compression',
        path: {
          cwd: '',
          root: ''
        },
        cost: 0,
        tokens: {
          input: 0,
          output: 0,
          reasoning: 0,
          cache: {
            read: 0,
            write: 0
          }
        }
      },
      parts: [
        {
          id: `${msgId}-part`,
          sessionID: 'headroom',
          messageID: msgId,
          type: 'text',
          text
        }
      ]
    };

    messages.splice(startIndex, endIndex - startIndex + 1, compressionMessage);
    logger.debug(`Applied compression block ${block.id}`);
  }
}

export function pruneParts(
  messages: MessageWithParts[],
  state: SessionState,
  logger: Logger
): void {
  let prunedCount = 0;

  for (const msg of messages) {
    msg.parts = msg.parts.filter((part) => {
      if (!('id' in part) || !part.id) return true;

      if (state.prunedPartIds.has(part.id)) {
        prunedCount++;
        return false;
      }

      return true;
    });
  }

  if (prunedCount > 0) {
    logger.debug(`Pruned ${prunedCount} parts from messages`);
  }
}
