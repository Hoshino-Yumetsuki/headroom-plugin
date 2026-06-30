import type {
  MessageWithParts,
  HeadroomConfig,
  SessionState,
  Logger,
  PriorityMap
} from '../types.ts';
import { resetSessionState } from '../compress/state.ts';
import {
  assignMessageIds,
  injectMessageIdTags,
  stripModelGeneratedMetadata
} from '../message-ids.ts';
import { getAllStrategies } from './registry.ts';
import { applyCompressionBlocks, pruneParts } from './prune.ts';
import { injectCompressionNudges } from '../nudge/inject.ts';
import './strategies/index.ts';

function filterMalformedMessages(messages: MessageWithParts[]): MessageWithParts[] {
  return messages.filter((msg) => {
    if (!msg.info?.id || !msg.info?.role) return false;
    if (!Array.isArray(msg.parts)) return false;
    return true;
  });
}

function checkSessionChange(
  messages: readonly MessageWithParts[],
  state: SessionState,
  logger: Logger
): void {
  if (messages.length === 0) return;

  const firstMessage = messages[0];
  if (!firstMessage) return;

  const sessionIdHint = firstMessage.info.id.split('-')[0];

  if (state.sessionId === null) {
    state.sessionId = sessionIdHint ?? null;
    logger.info(`Session initialized: ${state.sessionId}`);
  } else if (state.sessionId !== sessionIdHint) {
    logger.info(`Session changed: ${state.sessionId} → ${sessionIdHint}`);
    resetSessionState(state);
    state.sessionId = sessionIdHint ?? null;
  }
}

function buildPriorityMap(
  messages: readonly MessageWithParts[],
  config: HeadroomConfig
): PriorityMap {
  const low: string[] = [];
  const medium: string[] = [];
  const high: string[] = [];

  for (const msg of messages) {
    const msgId = msg.info.id;

    if (msg.info.role === 'user' && config.compress.protectUserMessages) {
      high.push(msgId);
      continue;
    }

    for (const part of msg.parts) {
      if (part.type === 'tool') {
        const toolName = part.tool ?? '';
        if (config.compress.protectedTools.includes(toolName)) {
          high.push(msgId);
          break;
        } else if (part.state?.status === 'error') {
          medium.push(msgId);
          break;
        } else {
          low.push(msgId);
          break;
        }
      }
    }
  }

  return { low, medium, high };
}

export function createMessageTransformPipeline(
  config: HeadroomConfig,
  state: SessionState,
  logger: Logger
) {
  return async (input: unknown, output: { messages: MessageWithParts[] }) => {
    output.messages = filterMalformedMessages(output.messages);

    checkSessionChange(output.messages, state, logger);

    stripModelGeneratedMetadata(output.messages);

    const idMap = assignMessageIds(output.messages);
    state.messageIdMap = idMap;
    state.shortIdMap = new Map(Array.from(idMap.entries()).map(([k, v]) => [v, k]));

    let bytesSavedThisTurn = 0;

    // Store original sizes for calculation
    const originalSizes = new Map<string, number>();
    for (const msg of output.messages) {
      for (const part of msg.parts) {
        if (part.id && part.type === 'tool' && part.state?.input) {
          originalSizes.set(part.id, JSON.stringify(part.state.input).length);
        }
      }
    }

    const strategies = getAllStrategies();
    for (const [_name, strategy] of strategies) {
      await strategy(output.messages, state, config, logger);
    }

    applyCompressionBlocks(output.messages, state, logger);

    pruneParts(output.messages, state, logger);

    // Calculate bytes saved by parts pruned or modified
    for (const msg of output.messages) {
      for (const part of msg.parts) {
        if (part.id && originalSizes.has(part.id)) {
          if (part.type === 'tool' && part.state?.input) {
            const newSize = JSON.stringify(part.state.input).length;
            const oldSize = originalSizes.get(part.id)!;
            if (newSize < oldSize) {
              bytesSavedThisTurn += oldSize - newSize;
            }
          }
        }
      }
    }

    // Add sizes of completely pruned parts
    for (const partId of state.prunedPartIds) {
      if (originalSizes.has(partId)) {
        bytesSavedThisTurn += originalSizes.get(partId)!;
      }
    }

    state.totalBytesSaved += bytesSavedThisTurn;

    const priorityMap = buildPriorityMap(output.messages, config);

    injectCompressionNudges(output.messages, config, state, logger, priorityMap);

    injectMessageIdTags(output.messages, idMap);

    state.turnCount++;
    state.fetchCount++;

    const lastMessage = output.messages[output.messages.length - 1];
    if (lastMessage?.info.role === 'user') {
      state.lastUserMessageTurn = state.turnCount;
    }

    logger.debug(
      `Message transform complete: ${output.messages.length} messages, turn ${state.turnCount}`
    );
  };
}
