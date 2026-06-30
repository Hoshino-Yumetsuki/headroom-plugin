import type { Plugin, PluginModule } from '@opencode-ai/plugin';
import { loadConfig } from './config.ts';
import { createLogger } from './logger.ts';
import { createSessionState } from './compress/index.ts';
import { createCompressTool } from './compress/range.ts';
import {
  createSystemPromptHook,
  createMessageTransformHook,
  createTextCompleteHook,
  createCommandHook,
  createEventHook
} from './hooks.ts';

const server: Plugin = async (ctx) => {
  const config = loadConfig(ctx);

  if (!config.enabled) {
    return {};
  }

  const state = createSessionState();
  const logger = createLogger();

  logger.info('Headroom plugin initialized');

  return {
    'experimental.chat.system.transform': createSystemPromptHook(config, state),
    'experimental.chat.messages.transform': createMessageTransformHook(config, state, logger),
    'experimental.text.complete': createTextCompleteHook(state),
    'command.execute.before': createCommandHook(config, state, logger),
    event: createEventHook(state, logger),
    tool: {
      compress: createCompressTool(config, state, logger)
    },
    config: async (opencodeConfig) => {
      opencodeConfig.command ??= {};
      opencodeConfig.command['headroom'] = {
        template: '',
        description: 'Show Headroom context pruning status'
      };
      opencodeConfig.command['headroom-compress'] = {
        template: '',
        description: 'Trigger manual context compression'
      };
      opencodeConfig.experimental = {
        ...opencodeConfig.experimental,
        primary_tools: [...(opencodeConfig.experimental?.primary_tools ?? []), 'compress']
      };
    }
  };
};

export default { id: 'opencode-headroom', server } satisfies PluginModule;
