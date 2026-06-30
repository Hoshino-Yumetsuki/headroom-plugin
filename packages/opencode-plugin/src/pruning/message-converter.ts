/**
 * Message format converter: OpenCode ↔ Anthropic
 */

import type { MessageWithParts, Logger } from '../types';
import type { Part } from '@opencode-ai/sdk';

export interface AnthropicMessage {
  role: 'user' | 'assistant';
  content: string | AnthropicContentBlock[];
}

export type AnthropicContentBlock =
  | AnthropicTextBlock
  | AnthropicToolUseBlock
  | AnthropicToolResultBlock;

export interface AnthropicTextBlock {
  type: 'text';
  text: string;
}

export interface AnthropicToolUseBlock {
  type: 'tool_use';
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface AnthropicToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content: string;
  is_error?: boolean;
}

export function toAnthropicFormat(
  messages: MessageWithParts[],
  logger?: Logger
): AnthropicMessage[] {
  logger?.debug('[Converter] Converting to Anthropic format', {
    messageCount: messages.length
  });

  const anthropicMessages: AnthropicMessage[] = [];
  const skippedTypes = new Map<string, number>(); // Track skipped part types

  for (const msg of messages) {
    try {
      const role = msg.info.role;

      if (role !== 'user' && role !== 'assistant') {
        continue;
      }

      const blocks: AnthropicContentBlock[] = [];

      for (const part of msg.parts) {
        const block = partToAnthropicBlock(part, skippedTypes);
        if (block) {
          blocks.push(block);
        }
      }

      if (blocks.length === 0) {
        continue;
      }

      let content: string | AnthropicContentBlock[];
      if (blocks.length === 1 && blocks[0]?.type === 'text') {
        const firstBlock = blocks[0] as AnthropicTextBlock;
        content = firstBlock.text;
      } else {
        content = blocks;
      }

      anthropicMessages.push({ role, content });
    } catch (err) {
      logger?.error('[Converter] Failed to convert message', {
        messageId: msg.info.id,
        error: String(err)
      });
    }
  }

  // Log summary of skipped types
  if (skippedTypes.size > 0) {
    const summary = Array.from(skippedTypes.entries())
      .map(([type, count]) => `${type}×${count}`)
      .join(', ');
    logger?.debug('[Converter] Skipped unsupported parts', { summary });
  }

  logger?.debug('[Converter] Conversion complete', {
    inputMessages: messages.length,
    outputMessages: anthropicMessages.length
  });

  return anthropicMessages;
}

export function fromAnthropicFormat(
  anthropicMessages: AnthropicMessage[],
  originalMessages: MessageWithParts[],
  logger?: Logger
): MessageWithParts[] {
  logger?.debug('[Converter] Converting from Anthropic format', {
    anthropicCount: anthropicMessages.length,
    originalCount: originalMessages.length
  });

  const result: MessageWithParts[] = [];

  for (let i = 0; i < anthropicMessages.length; i++) {
    const anthroMsg = anthropicMessages[i];

    if (!anthroMsg) continue;

    try {
      const original = findMatchingOriginal(anthroMsg, i, originalMessages);

      if (!original) {
        logger?.warn('[Converter] No matching original message found', {
          index: i,
          role: anthroMsg.role
        });
        continue;
      }

      const parts = anthropicContentToParts(anthroMsg.content, original.parts, logger);

      result.push({
        info: original.info,
        parts
      });

      logger?.debug('[Converter] Converted back to OpenCode format', {
        messageId: original.info.id,
        partCount: parts.length
      });
    } catch (err) {
      logger?.error('[Converter] Failed to convert from Anthropic', {
        index: i,
        error: String(err)
      });
    }
  }

  logger?.debug('[Converter] Reverse conversion complete', {
    inputCount: anthropicMessages.length,
    outputCount: result.length
  });

  return result;
}

function partToAnthropicBlock(
  part: Part,
  skippedTypes: Map<string, number>
): AnthropicContentBlock | null {
  if (part.type === 'text') {
    return {
      type: 'text',
      text: part.text || ''
    };
  }

  if (part.type === 'tool') {
    const toolPart = part as any;
    const state = toolPart.state;

    if (state.status === 'pending' || state.status === 'running') {
      return {
        type: 'tool_use',
        id: toolPart.callID,
        name: toolPart.tool,
        input: state.input || {}
      };
    }

    if (state.status === 'completed' || state.status === 'error') {
      return {
        type: 'tool_result',
        tool_use_id: toolPart.callID,
        content: state.output || state.error || '',
        is_error: state.status === 'error'
      };
    }
  }

  // Track skipped types for summary
  const count = skippedTypes.get(part.type) || 0;
  skippedTypes.set(part.type, count + 1);

  return null;
}

function findMatchingOriginal(
  anthroMsg: AnthropicMessage,
  index: number,
  originals: MessageWithParts[]
): MessageWithParts | null {
  const candidate = originals[index];
  if (candidate && candidate.info.role === anthroMsg.role) {
    return candidate;
  }

  const roleMatches = originals.filter((m) => m.info.role === anthroMsg.role);
  if (roleMatches.length > 0) {
    return roleMatches[Math.min(index, roleMatches.length - 1)] || null;
  }

  return null;
}

function anthropicContentToParts(
  content: string | AnthropicContentBlock[],
  originalParts: Part[],
  logger?: Logger
): Part[] {
  if (typeof content === 'string') {
    const originalTextPart = originalParts.find((p) => p.type === 'text');

    if (originalTextPart && originalTextPart.type === 'text') {
      return [
        {
          ...originalTextPart,
          text: content
        }
      ];
    }

    return [
      {
        id: 'text_0',
        sessionID: originalParts[0]?.sessionID || '',
        messageID: originalParts[0]?.messageID || '',
        type: 'text',
        text: content
      } as Part
    ];
  }

  const parts: Part[] = [];

  for (let i = 0; i < content.length; i++) {
    const block = content[i];

    if (!block) continue;

    try {
      if (block.type === 'text') {
        const textBlock = block as AnthropicTextBlock;
        const originalTextPart = originalParts.find((p) => p.type === 'text');

        if (originalTextPart && originalTextPart.type === 'text') {
          parts.push({
            ...originalTextPart,
            text: textBlock.text
          });
        } else {
          parts.push({
            id: `text_${i}`,
            sessionID: originalParts[0]?.sessionID || '',
            messageID: originalParts[0]?.messageID || '',
            type: 'text',
            text: textBlock.text
          } as Part);
        }
      } else if (block.type === 'tool_use') {
        const toolUseBlock = block as AnthropicToolUseBlock;
        const originalToolPart = originalParts.find(
          (p) => p.type === 'tool' && (p as any).callID === toolUseBlock.id
        );

        if (originalToolPart && originalToolPart.type === 'tool') {
          parts.push(originalToolPart);
        } else {
          parts.push({
            id: `tool_${i}`,
            sessionID: originalParts[0]?.sessionID || '',
            messageID: originalParts[0]?.messageID || '',
            type: 'tool',
            callID: toolUseBlock.id,
            tool: toolUseBlock.name,
            state: {
              status: 'pending',
              input: toolUseBlock.input,
              raw: JSON.stringify(toolUseBlock.input)
            }
          } as Part);
        }
      } else if (block.type === 'tool_result') {
        const toolResultBlock = block as AnthropicToolResultBlock;
        const originalToolPart = originalParts.find(
          (p) => p.type === 'tool' && (p as any).callID === toolResultBlock.tool_use_id
        );

        if (originalToolPart && originalToolPart.type === 'tool') {
          const toolPart = originalToolPart as any;
          parts.push({
            ...toolPart,
            state: {
              ...toolPart.state,
              status: toolResultBlock.is_error ? 'error' : 'completed',
              [toolResultBlock.is_error ? 'error' : 'output']: toolResultBlock.content
            }
          } as Part);
        } else {
          parts.push({
            id: `tool_result_${i}`,
            sessionID: originalParts[0]?.sessionID || '',
            messageID: originalParts[0]?.messageID || '',
            type: 'tool',
            callID: toolResultBlock.tool_use_id,
            tool: 'unknown',
            state: toolResultBlock.is_error
              ? {
                  status: 'error',
                  input: {},
                  error: toolResultBlock.content,
                  time: { start: Date.now(), end: Date.now() }
                }
              : {
                  status: 'completed',
                  input: {},
                  output: toolResultBlock.content,
                  title: '',
                  metadata: {},
                  time: { start: Date.now(), end: Date.now() }
                }
          } as Part);
        }
      }
    } catch (err) {
      logger?.error('[Converter] Failed to convert block', {
        blockIndex: i,
        blockType: block.type,
        error: String(err)
      });
    }
  }

  return parts;
}
