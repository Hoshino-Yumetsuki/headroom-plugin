import type { PruningStrategy } from '../../types.ts';
import { registerStrategy } from '../registry.ts';

const staleContextStrategy: PruningStrategy = async (messages, state, config, logger) => {
  if (!config.strategies.staleContext.enabled) return;

  const fileReads = new Map<string, { partId: string; messageIndex: number }[]>();

  for (let msgIndex = 0; msgIndex < messages.length; msgIndex++) {
    const msg = messages[msgIndex];
    if (!msg) continue;

    for (const part of msg.parts) {
      if (part.type !== 'tool') continue;
      if (!('id' in part) || !part.id) continue;

      const toolName = part.tool ?? '';
      if (!['read', 'file'].includes(toolName)) continue;

      const input = part.state?.input;
      if (!input || typeof input !== 'object') continue;

      const filePath =
        'filePath' in input && typeof input.filePath === 'string'
          ? input.filePath
          : 'path' in input && typeof input.path === 'string'
            ? input.path
            : null;

      if (!filePath) continue;

      if (!fileReads.has(filePath)) {
        fileReads.set(filePath, []);
      }

      fileReads.get(filePath)?.push({ partId: part.id, messageIndex: msgIndex });
    }
  }

  let prunedCount = 0;

  for (const [filePath, reads] of fileReads.entries()) {
    if (reads.length <= 1) continue;

    reads.sort((a, b) => a.messageIndex - b.messageIndex);

    for (let i = 0; i < reads.length - 1; i++) {
      const read = reads[i];
      if (!read) continue;
      state.prunedPartIds.add(read.partId);
      prunedCount++;
      logger.debug(`Marked stale file read for pruning: ${filePath} (part ${read.partId})`);
    }
  }

  if (prunedCount > 0) {
    logger.info(`Stale context strategy: marked ${prunedCount} stale file reads for pruning`);
  }
};

registerStrategy('staleContext', staleContextStrategy);

export { staleContextStrategy };
