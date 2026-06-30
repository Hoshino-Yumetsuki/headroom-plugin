import { spawn } from 'node:child_process';
import type { MessageWithParts, Logger } from './types.ts';

export interface CompressRequest {
  command: 'compress';
  prescription: 'gentle' | 'standard' | 'aggressive';
  session: {
    id: string;
    context_window: number;
    current_usage: number;
  };
  messages: Array<{
    id: string;
    role: string;
    timestamp: number;
    parts: Array<{
      id: string;
      type: string;
      content?: string;
      tool?: string;
      input?: unknown;
      output?: string;
      size_bytes: number;
    }>;
  }>;
}

export interface CompressResponse {
  status: 'success' | 'error';
  error?: string;
  details?: string;
  summary?: {
    original_size: number;
    compressed_size: number;
    savings_bytes: number;
    savings_percent: number;
  };
  actions?: Array<{
    action: string;
    part_id: string;
    reason: string;
    strategy: string;
    savings_bytes: number;
  }>;
}

/**
 * Call Python CLI via JSON stdin/stdout pipe.
 */
export async function callPythonCLI(
  cliPath: string,
  request: CompressRequest,
  logger: Logger
): Promise<CompressResponse> {
  return new Promise((resolve, reject) => {
    const args = ['compress', '--rx', request.prescription];
    const cli = spawn(cliPath, args);

    let stdout = '';
    let stderr = '';

    cli.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    cli.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    cli.on('close', (code) => {
      if (code !== 0) {
        logger.error(`Python CLI exited with code ${code}`, {
          stderr: stderr.trim()
        });
        reject(new Error(`CLI exited with code ${code}: ${stderr}`));
        return;
      }

      try {
        const response: CompressResponse = JSON.parse(stdout);
        resolve(response);
      } catch (err) {
        logger.error('Failed to parse Python CLI output', {
          stdout: stdout.slice(0, 500),
          error: String(err)
        });
        reject(new Error(`Failed to parse CLI output: ${err}`));
      }
    });

    cli.on('error', (err) => {
      logger.error('Failed to spawn Python CLI', { error: String(err) });
      reject(new Error(`Failed to spawn CLI: ${err}`));
    });

    // Write request JSON to stdin
    try {
      cli.stdin.write(JSON.stringify(request));
      cli.stdin.end();
    } catch (err) {
      logger.error('Failed to write to Python CLI stdin', { error: String(err) });
      reject(new Error(`Failed to write to CLI stdin: ${err}`));
    }
  });
}

/**
 * Convert MessageWithParts to generic JSON format for Python CLI.
 */
export function messagesToJSON(
  messages: MessageWithParts[],
  sessionId: string
): CompressRequest['messages'] {
  return messages.map((msg) => ({
    id: msg.info.id,
    role: msg.info.role,
    timestamp: Date.now(), // OpenCode doesn't expose timestamp directly
    parts: msg.parts.map((part) => {
      let content: string | undefined;
      let tool: string | undefined;
      let input: unknown | undefined;
      let output: string | undefined;

      if (part.type === 'text') {
        content = part.text;
      } else if (part.type === 'tool') {
        tool = part.tool ?? 'unknown';
        if (part.state) {
          if (part.state.status === 'completed') {
            output = JSON.stringify(part.state.output);
          } else if (part.state.status === 'error') {
            output = part.state.error;
          }
          input = part.state.input;
        }
      }

      // Estimate size in bytes
      const sizeEstimate = JSON.stringify(part).length;

      return {
        id: part.id,
        type: part.type,
        content,
        tool,
        input,
        output,
        size_bytes: sizeEstimate
      };
    })
  }));
}
