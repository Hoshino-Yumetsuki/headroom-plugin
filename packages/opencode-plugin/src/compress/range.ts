import { tool } from '@opencode-ai/plugin';
import type { HeadroomConfig, SessionState, Logger, CompressionBlock } from '../types.ts';
import type { CompressArgs } from './types.ts';
import { calculateByteSize } from '../token-utils.ts';

export function createCompressTool(config: HeadroomConfig, state: SessionState, logger: Logger) {
  return tool({
    description: `Compress a range of conversation messages into a concise summary to reduce context window usage. 
Specify message IDs using the <headroom-id> tags visible in the conversation (e.g., m0001, m0012).
Write concise summaries that preserve: key decisions, file paths modified, error resolutions, and current task state.
This is the primary tool for managing long conversations.`,
    args: {
      startId: tool.schema.string().describe('Start message ID (e.g. m0001)'),
      endId: tool.schema.string().describe('End message ID (e.g. m0012)'),
      summary: tool.schema
        .string()
        .describe('Concise summary preserving key decisions, file paths, and outcomes')
    },
    async execute(args: CompressArgs, _ctx) {
      logger.info(`Compress request: ${args.startId} to ${args.endId}`);

      const startMessageId = state.shortIdMap.get(args.startId);
      const endMessageId = state.shortIdMap.get(args.endId);

      if (!startMessageId || !endMessageId) {
        return {
          output: `Error: Invalid message IDs: ${args.startId} or ${args.endId} not found`
        };
      }

      // Note: We rely on the message transform hook to have cached message structure in state
      // The actual compression will be applied on the next message fetch
      const blockId = `b${state.compressionBlocks.length + 1}`;
      const block: CompressionBlock = {
        id: blockId,
        startMessageId,
        endMessageId,
        summary: args.summary,
        originalByteSize: 0, // Will be calculated on next transform
        compressedByteSize: calculateByteSize(args.summary),
        messageCount: 0, // Will be counted on next transform
        createdAt: Date.now()
      };

      state.compressionBlocks.push(block);
      logger.info(`Compression block ${blockId} created`);

      return {
        output:
          `✓ Compression block registered (${args.startId} to ${args.endId})\n` +
          `Summary: ${args.summary}\n` +
          `Block ID: ${blockId}\n\n` +
          `This compression will be applied on the next message fetch.`
      };
    }
  });
}
