import type {
  MessageWithParts,
  HeadroomConfig,
  SessionState,
  Logger,
} from '../types.ts';
import { resetSessionState } from '../compress/state.ts';
import {
  assignMessageIds,
  injectMessageIdTags,
  stripModelGeneratedMetadata
} from '../message-ids.ts';
import { callPythonCLI, messagesToJSON, type CompressRequest } from '../cli-bridge.ts';
import { injectCompressionNudges } from '../nudge/inject.ts';

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
    logger.info('Session initialized', { sessionId: state.sessionId });
  } else if (state.sessionId !== sessionIdHint) {
    logger.info('Session changed', { 
      oldSession: state.sessionId, 
      newSession: sessionIdHint 
    });
    resetSessionState(state);
    state.sessionId = sessionIdHint ?? null;
  }
}

/**
 * Apply compression actions returned from Python CLI.
 */
function applyCompressionActions(
  messages: MessageWithParts[],
  actions: CompressRequest['messages'],
  state: SessionState,
  logger: Logger
): number {
  let bytesSaved = 0;

  for (const action of actions) {
    if (action.action === 'delete_part') {
      // Find and mark part for deletion
      for (const msg of messages) {
        const partIndex = msg.parts.findIndex(p => p.id === action.part_id);
        if (partIndex !== -1) {
          const part = msg.parts[partIndex];
          state.prunedPartIds.add(action.part_id);
          bytesSaved += action.savings_bytes || 0;
          
          logger.debug('Pruning part', {
            partId: action.part_id,
            reason: action.reason,
            strategy: action.strategy,
            savings: action.savings_bytes
          });
          
          // Remove the part
          msg.parts.splice(partIndex, 1);
          break;
        }
      }
    }
  }

  return bytesSaved;
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

    // Call Python CLI for compression recommendations
    try {
      const request: CompressRequest = {
        command: 'compress',
        prescription: config.cli.prescription,
        session: {
          id: state.sessionId || 'unknown',
          context_window: 200000, // Could be made configurable
          current_usage: 0 // Could calculate from message sizes
        },
        messages: messagesToJSON(output.messages, state.sessionId || 'unknown')
      };

      logger.debug('Calling Python CLI', {
        prescription: request.prescription,
        messageCount: request.messages.length
      });

      const response = await callPythonCLI(config.cli.path, request, logger);

      if (response.status === 'success' && response.actions) {
        const bytesSaved = applyCompressionActions(
          output.messages,
          response.actions as any,
          state,
          logger
        );

        state.totalBytesSaved += bytesSaved;

        logger.info('Compression applied', {
          actions: response.actions.length,
          bytesSaved,
          savingsPercent: response.summary?.savings_percent
        });
      } else if (response.status === 'error') {
        logger.error('Python CLI returned error', {
          error: response.error,
          details: response.details
        });
      }
    } catch (err) {
      logger.error('Failed to call Python CLI', { error: String(err) });
      // Continue without compression rather than failing the whole request
    }

    // Inject compression nudges if needed
    const priorityMap = { low: [], medium: [], high: [] };
    injectCompressionNudges(output.messages, config, state, logger, priorityMap);

    injectMessageIdTags(output.messages, idMap);

    state.turnCount++;
    state.fetchCount++;

    const lastMessage = output.messages[output.messages.length - 1];
    if (lastMessage?.info.role === 'user') {
      state.lastUserMessageTurn = state.turnCount;
    }

    logger.debug('Message transform complete', {
      messageCount: output.messages.length,
      turn: state.turnCount,
      requestId: state.requestId
    });
  };
}
