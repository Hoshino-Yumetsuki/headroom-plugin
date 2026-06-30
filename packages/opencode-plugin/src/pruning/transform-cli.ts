/**
 * CLI-based compression transform using headroom SDK
 */

import type {
  MessageWithParts,
  HeadroomConfig,
  SessionState,
  Logger,
} from '../types.ts';
import { resetSessionState } from '../compress/state.ts';
import { stripModelGeneratedMetadata } from '../message-ids.ts';
import { toAnthropicFormat, fromAnthropicFormat } from './message-converter.ts';
import { spawn } from 'node:child_process';

interface CLIRequest {
  messages: any[];
  prescription: string;
  model?: string;
  context_window?: number;
}

interface CLIResponse {
  status: 'success' | 'error';
  messages?: any[];
  tokens_before?: number;
  tokens_after?: number;
  tokens_saved?: number;
  compression_ratio?: number;
  error?: string;
  error_type?: string;
}

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
 * Call Python CLI with JSON request/response
 */
async function callCLI(
  cliPath: string,
  request: CLIRequest,
  logger: Logger
): Promise<CLIResponse> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cliPath, [], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        logger.error('CLI process failed', { code, stderr });
        reject(new Error(`CLI exited with code ${code}: ${stderr}`));
        return;
      }

      try {
        const response = JSON.parse(stdout);
        resolve(response);
      } catch (e) {
        logger.error('Failed to parse CLI response', { stdout, error: String(e) });
        reject(new Error(`Invalid JSON from CLI: ${e}`));
      }
    });

    proc.on('error', (err) => {
      logger.error('Failed to spawn CLI', { error: String(err) });
      reject(err);
    });

    // Send request
    proc.stdin.write(JSON.stringify(request));
    proc.stdin.end();
  });
}

/**
 * Main compression transform using CLI
 */
export async function transform(
  output: { messages: MessageWithParts[] },
  config: HeadroomConfig,
  state: SessionState,
  logger: Logger
): Promise<void> {
  logger.debug('CLI transform start', { messageCount: output.messages.length });

  // Filter and validate
  output.messages = filterMalformedMessages(output.messages);
  checkSessionChange(output.messages, state, logger);
  stripModelGeneratedMetadata(output.messages);

  // Convert to Anthropic format
  const anthropicMessages = toAnthropicFormat(output.messages);

  logger.debug('Converted to Anthropic format', {
    originalCount: output.messages.length,
    anthropicCount: anthropicMessages.length
  });

  // Call Python CLI
  try {
    const request: CLIRequest = {
      messages: anthropicMessages,
      prescription: config.cli.prescription,
      model: 'claude-sonnet-4-5-20250929',
      context_window: 200000
    };

    logger.debug('Calling Python CLI', { prescription: request.prescription });

    const response = await callCLI(config.cli.path, request, logger);

    if (response.status === 'success' && response.messages) {
      // Convert back to OpenCode format
      const compressedMessages = fromAnthropicFormat(response.messages, output.messages);

      const bytesSaved = response.tokens_saved || 0;
      state.totalBytesSaved += bytesSaved;

      logger.info('Compression applied', {
        tokensRemoved: bytesSaved,
        compressionRatio: response.compression_ratio,
        messagesBefore: output.messages.length,
        messagesAfter: compressedMessages.length
      });

      // Replace messages with compressed version
      output.messages = compressedMessages;
    } else if (response.status === 'error') {
      logger.error('CLI returned error', {
        error: response.error,
        errorType: response.error_type
      });
    }
  } catch (err) {
    logger.error('Failed to call CLI', { error: String(err) });
    // Continue without compression rather than failing
  }

  logger.debug('CLI transform complete');
}

/**
 * Create message transform pipeline (for compatibility with hooks.ts)
 */
export function createMessageTransformPipeline(
  config: HeadroomConfig,
  state: SessionState,
  logger: Logger
) {
  return async (output: { messages: MessageWithParts[] }) => {
    await transform(output, config, state, logger);
  };
}
