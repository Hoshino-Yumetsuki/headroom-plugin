/**
 * Message transformation via Python CLI using stdin/stdout
 */

import { spawn } from 'node:child_process';
import type { HeadroomConfig, SessionState, Logger, MessageWithParts } from '../types';
import { toAnthropicFormat, fromAnthropicFormat } from './message-converter';
import type { AnthropicMessage } from './message-converter';

interface CLIRequest {
  messages: AnthropicMessage[];
  prescription: string;
  model: string;
  context_window: number;
}

interface CLISuccessResponse {
  status: 'success';
  messages: AnthropicMessage[];
  tokens_before: number;
  tokens_after: number;
  tokens_saved: number;
  compression_ratio: number;
}

interface CLIErrorResponse {
  status: 'error';
  error: string;
  error_type: string;
  details?: string;
}

type CLIResponse = CLISuccessResponse | CLIErrorResponse;

/**
 * Call Python CLI via stdin/stdout with proper binary handling
 */
async function callCLI(cliPath: string, request: CLIRequest, logger: Logger): Promise<CLIResponse> {
  const seenObjects = new WeakSet<object>();

  return new Promise((resolve, reject) => {
    logger.debug('Spawning CLI process', { cliPath });

    // Spawn without shell to avoid text mode conversion
    const proc = spawn(cliPath, [], {
      stdio: ['pipe', 'pipe', 'pipe'],
      shell: false,
      windowsHide: true
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString('utf8');
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString('utf8');
    });

    proc.on('close', (code) => {
      logger.debug('CLI process closed', {
        code,
        stdoutLength: stdout.length,
        stderrLength: stderr.length
      });

      // Try to parse response first - Python warnings may go to stderr but still succeed
      let response: CLIResponse | null = null;
      try {
        response = JSON.parse(stdout) as CLIResponse;
      } catch {
        // stdout is not valid JSON
      }

      // If we got a valid response with success status, ignore exit code and stderr warnings
      if (response && response.status === 'success') {
        logger.debug('CLI response parsed', { status: response.status });
        resolve(response);
        return;
      }

      // Otherwise, check exit code
      if (code !== 0) {
        logger.error('CLI process failed', { code, stderr, stdout });
        reject(new Error(`CLI exited with code ${code}: ${stderr || stdout}`));
        return;
      }

      // Exit code 0 but no valid response
      if (!response) {
        const errorMessage = 'Invalid JSON from CLI';
        logger.error('Failed to parse CLI response', { error: errorMessage });
        reject(new Error(errorMessage));
        return;
      }

      // Exit code 0 and valid response
      logger.debug('CLI response parsed', { status: response.status });
      resolve(response);
    });

    proc.on('error', (err) => {
      logger.error('Failed to spawn CLI', { error: String(err) });
      reject(new Error(`Failed to spawn CLI: ${err.message}`));
    });

    // Serialize request with safe handling
    let requestJson: string;
    try {
      requestJson = JSON.stringify(request, (_key, value) => {
        if (value === undefined || typeof value === 'function' || typeof value === 'symbol') {
          return null;
        }
        if (value !== null && typeof value === 'object') {
          if (seenObjects.has(value)) {
            return '[Circular]';
          }
          seenObjects.add(value);
        }
        return value;
      });
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      logger.error('Failed to stringify request', { error: errorMessage });
      reject(new Error(`JSON stringify failed: ${errorMessage}`));
      return;
    }

    logger.debug('Sending request to CLI', { requestLength: requestJson.length });

    // Write as UTF-8 buffer to avoid encoding issues
    const buffer = Buffer.from(requestJson, 'utf8');

    try {
      proc.stdin.write(buffer);
      proc.stdin.end();
      logger.debug('Request written to CLI stdin', { bytes: buffer.length });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      logger.error('Failed to write to CLI stdin', { error: errorMessage });
      reject(new Error(`Failed to write to stdin: ${errorMessage}`));
    }
  });
}

/**
 * Transform messages via CLI
 */
export async function transform(
  output: { messages: MessageWithParts[] },
  config: HeadroomConfig,
  state: SessionState,
  logger: Logger
): Promise<void> {
  try {
    logger.debug('CLI transform start', { messageCount: output.messages.length });

    if (output.messages.length === 0) {
      logger.debug('No messages to compress');
      return;
    }

    // Convert to Anthropic format
    const anthropicMessages = toAnthropicFormat(output.messages, logger);
    logger.debug('Converted to Anthropic format', {
      originalCount: output.messages.length,
      anthropicCount: anthropicMessages.length
    });

    if (anthropicMessages.length === 0) {
      logger.warn('No messages after conversion');
      return;
    }

    // Prepare CLI request
    const request: CLIRequest = {
      messages: anthropicMessages,
      prescription: config.cli.prescription,
      model: 'claude-sonnet-4',
      context_window: 200000
    };

    logger.debug('Calling Python CLI', {
      prescription: request.prescription,
      messageCount: request.messages.length,
      cliPath: config.cli.path
    });

    // Call CLI
    const response = await callCLI(config.cli.path, request, logger);

    if (response.status === 'success') {
      // Convert back to OpenCode format
      const compressedMessages = fromAnthropicFormat(response.messages, output.messages, logger);

      if (compressedMessages.length === 0) {
        logger.warn('No messages after reverse conversion');
        return;
      }

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
    logger.error('Failed to call CLI', {
      error: String(err),
      stack: err instanceof Error ? err.stack : undefined
    });
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
  return async (_input: Record<string, never>, output: { messages: MessageWithParts[] }) => {
    await transform(output, config, state, logger);
  };
}
