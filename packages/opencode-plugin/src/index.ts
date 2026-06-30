import type { Plugin, PluginModule, Hooks } from '@opencode-ai/plugin';
import { loadConfig } from './config.ts';
import { createLogger } from './logger.ts';
import { createSessionState } from './compress/index.ts';
import {
  createSystemPromptHook,
  createMessageTransformHook,
  createTextCompleteHook,
  createEventHook
} from './hooks.ts';

const server: Plugin = async (ctx, _options): Promise<Hooks> => {
  const config = loadConfig(ctx);

  if (!config.enabled) {
    return {};
  }

  const state = createSessionState();
  const logger = createLogger(config);

  logger.info('Headroom plugin initialized', { requestId: state.requestId });

  return {
    'experimental.chat.system.transform': createSystemPromptHook(config, state),
    'experimental.chat.messages.transform': createMessageTransformHook(config, state, logger),
    'experimental.text.complete': createTextCompleteHook(state),
    event: createEventHook(state, logger)
  };
};

export default { id: 'opencode-headroom', server } satisfies PluginModule;
