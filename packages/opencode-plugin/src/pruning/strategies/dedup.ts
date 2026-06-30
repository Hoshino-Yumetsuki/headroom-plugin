import type { PruningStrategy } from '../../types.ts';
import { registerStrategy } from '../registry.ts';

const deduplicationStrategy: PruningStrategy = async (messages, state, config, logger) => {
  if (!config.strategies.deduplication.enabled) return;

  const signatures = new Map<string, { partId: string; messageIndex: number; partIndex: number }>();
  const toPrune = new Set<string>();

  for (let msgIndex = 0; msgIndex < messages.length; msgIndex++) {
    const msg = messages[msgIndex];
    if (!msg) continue;

    for (let partIndex = 0; partIndex < msg.parts.length; partIndex++) {
      const part = msg.parts[partIndex];
      if (!part || part.type !== 'tool') continue;
      if (!('id' in part) || !part.id) continue;

      const toolName = part.tool ?? 'unknown';
      const input = part.state?.input ?? {};

      const sortedKeys = Object.keys(input).sort();
      const sortedInput: Record<string, unknown> = {};
      for (const key of sortedKeys) {
        sortedInput[key] = input[key];
      }

      const signature = `${toolName}::${JSON.stringify(sortedInput)}`;

      const existing = signatures.get(signature);
      if (existing) {
        toPrune.add(existing.partId);
        logger.debug(`Marking duplicate tool call for pruning: ${existing.partId}`);
      }

      signatures.set(signature, { partId: part.id, messageIndex: msgIndex, partIndex });
      state.toolCache.set(signature, {
        signature,
        partId: part.id,
        messageId: msg.info.id,
        turnIndex: msgIndex
      });
    }
  }

  for (const partId of toPrune) {
    state.prunedPartIds.add(partId);
  }

  if (toPrune.size > 0) {
    logger.info(`Deduplication strategy: marked ${toPrune.size} duplicate tool calls for pruning`);
  }
};

registerStrategy('deduplication', deduplicationStrategy);

export { deduplicationStrategy };
