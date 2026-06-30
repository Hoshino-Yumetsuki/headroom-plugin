import type { HeadroomConfig, SessionState, Logger } from './types.ts';
import { createSystemPromptHandler } from './nudge/system.ts';
import { createMessageTransformPipeline } from './pruning/transform.ts';
import { createCommandHandler } from './commands/handler.ts';

export function createSystemPromptHook(config: HeadroomConfig, state: SessionState) {
  return createSystemPromptHandler(config, state);
}

export function createMessageTransformHook(
  config: HeadroomConfig,
  state: SessionState,
  logger: Logger
) {
  return createMessageTransformPipeline(config, state, logger);
}

export function createTextCompleteHook(_state: SessionState) {
  return async (_input: unknown, _output: unknown) => {
    // Text complete hook placeholder
    // Could be used for inline completion filtering in the future
  };
}

export function createCommandHook(config: HeadroomConfig, state: SessionState, logger: Logger) {
  return createCommandHandler(config, state, logger);
}

export function createEventHook(state: SessionState, logger: Logger) {
  return async (input: { event: { type: string; properties?: unknown } }) => {
    const eventType = input.event.type;

    if (eventType === 'session.start') {
      logger.info('Session start event received');
    }

    if (eventType === 'session.end') {
      logger.info('Session end event received');
    }
  };
}
