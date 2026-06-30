import type {
  MessageWithParts,
  HeadroomConfig,
  SessionState,
  Logger,
  PriorityMap
} from '../types.ts';
import { estimateTokenCount } from '../token-utils.ts';

function calculateTotalTokens(messages: readonly MessageWithParts[]): number {
  let total = 0;
  for (const msg of messages) {
    for (const part of msg.parts) {
      if (part.type === 'text') {
        total += estimateTokenCount(part.text);
      } else if (part.type === 'tool' && part.state?.input) {
        total += estimateTokenCount(JSON.stringify(part.state.input));
      }
    }
  }
  return total;
}

function buildNudgeMessage(
  severity: 'soft' | 'strong' | 'iteration',
  contextTokens: number,
  maxLimit: number,
  priorityMap: PriorityMap
): MessageWithParts {
  let text = '';

  if (severity === 'soft') {
    text =
      `💡 Context growing: ${contextTokens.toLocaleString()} tokens (limit: ${maxLimit.toLocaleString()}). ` +
      `Consider using the compress tool to summarize completed work.`;
  } else if (severity === 'strong') {
    text =
      `⚠️ Context high: ${contextTokens.toLocaleString()} tokens (limit: ${maxLimit.toLocaleString()}). ` +
      `Strongly recommend compressing older message ranges now.\n\n` +
      `Priority guidance:\n` +
      `- High priority to keep: ${priorityMap.high.slice(0, 3).join(', ')}\n` +
      `- Medium priority: ${priorityMap.medium.slice(0, 3).join(', ')}\n` +
      `- Low priority (compress first): ${priorityMap.low.slice(0, 3).join(', ')}`;
  } else {
    text = `🔄 Many iterations without user input. Consider compressing the working phase to maintain context clarity.`;
  }

  const now = Date.now();
  const msgId = `headroom-nudge-${now}`;

  return {
    info: {
      id: msgId,
      sessionID: 'headroom',
      role: 'assistant',
      time: {
        created: now
      },
      parentID: 'system',
      modelID: 'headroom',
      providerID: 'headroom',
      mode: 'nudge',
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
}

export function injectCompressionNudges(
  messages: MessageWithParts[],
  config: HeadroomConfig,
  state: SessionState,
  logger: Logger,
  priorityMap: PriorityMap
): void {
  const contextTokens = calculateTotalTokens(messages);
  const { maxContextLimit, minContextLimit, nudgeFrequency, iterationNudgeThreshold } =
    config.compress;

  const iterationsSinceUser = state.turnCount - state.lastUserMessageTurn;

  if (contextTokens > maxContextLimit) {
    if (state.fetchCount - state.nudgeAnchor >= nudgeFrequency) {
      const nudge = buildNudgeMessage('strong', contextTokens, maxContextLimit, priorityMap);
      messages.push(nudge);
      state.nudgeAnchor = state.fetchCount;
      logger.info(`Injected strong nudge at ${contextTokens} tokens`);
    }
  } else if (contextTokens > minContextLimit) {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.info.role === 'user') {
      const nudge = buildNudgeMessage('soft', contextTokens, maxContextLimit, priorityMap);
      messages.push(nudge);
      logger.debug(`Injected soft nudge at ${contextTokens} tokens`);
    }
  }

  if (iterationsSinceUser > iterationNudgeThreshold) {
    const nudge = buildNudgeMessage('iteration', contextTokens, maxContextLimit, priorityMap);
    messages.push(nudge);
    logger.debug(`Injected iteration nudge after ${iterationsSinceUser} turns`);
  }
}
