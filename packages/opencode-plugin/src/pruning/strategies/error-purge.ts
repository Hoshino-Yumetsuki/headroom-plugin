import type { PruningStrategy } from '../../types.ts';
import { registerStrategy } from '../registry.ts';

const errorPurgeStrategy: PruningStrategy = async (messages, state, config, logger) => {
  if (!config.strategies.purgeErrors.enabled) return;

  const errorThreshold = config.strategies.purgeErrors.turns;
  const currentTurn = state.turnCount;
  let prunedCount = 0;

  for (let msgIndex = 0; msgIndex < messages.length; msgIndex++) {
    const msg = messages[msgIndex];
    if (!msg) continue;

    for (const part of msg.parts) {
      if (part.type !== 'tool') continue;
      if (!('id' in part) || !part.id) continue;
      if (part.state?.status !== 'error') continue;

      const turnsSinceError = currentTurn - msgIndex;
      if (turnsSinceError > errorThreshold) {
        if (part.state.input && typeof part.state.input === 'object') {
          const originalSize = JSON.stringify(part.state.input).length;
          part.state.input = {
            __pruned: 'error input removed after N turns',
            __original_size: originalSize
          };
          prunedCount++;
          logger.debug(`Pruned error input for part ${part.id} (${turnsSinceError} turns old)`);
        }
      }
    }
  }

  if (prunedCount > 0) {
    logger.info(`Error purge strategy: pruned ${prunedCount} error inputs`);
  }
};

registerStrategy('purgeErrors', errorPurgeStrategy);

export { errorPurgeStrategy };
