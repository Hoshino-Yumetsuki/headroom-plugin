/**
 * Message format converter: OpenCode ↔ Anthropic
 */

import type { MessageWithParts } from '../types';
import type { Part } from '@opencode-ai/sdk';

/**
 * Anthropic message format
 */
export interface AnthropicMessage {
  role: 'user' | 'assistant' | 'system';
  content: string | AnthropicContentBlock[];
}

export interface AnthropicContentBlock {
  type: 'text' | 'tool_use' | 'tool_result';
  text?: string;
  id?: string;
  name?: string;
  input?: any;
  tool_use_id?: string;
  content?: string;
}

/**
 * Convert OpenCode messages to Anthropic format
 */
export function toAnthropicFormat(messages: MessageWithParts[]): AnthropicMessage[] {
  return messages
    .map(msg => {
      const contentBlocks = msg.parts.map(part => partToAnthropicBlock(part)).filter(Boolean);
      
      if (contentBlocks.length === 0) {
        return null;
      }
      
      // Simplify if only one text block
      if (contentBlocks.length === 1 && contentBlocks[0].type === 'text') {
        return {
          role: msg.role as 'user' | 'assistant',
          content: contentBlocks[0].text!
        };
      }
      
      return {
        role: msg.role as 'user' | 'assistant',
        content: contentBlocks
      };
    })
    .filter((msg): msg is AnthropicMessage => msg !== null);
}

/**
 * Convert Anthropic messages back to OpenCode format
 */
export function fromAnthropicFormat(
  anthropicMessages: AnthropicMessage[],
  originalMessages: MessageWithParts[]
): MessageWithParts[] {
  // Create mapping from role+index to original message
  const roleIndices: Map<string, number> = new Map();
  
  return anthropicMessages.map((anthroMsg, idx) => {
    // Find corresponding original message
    const roleKey = anthroMsg.role;
    const roleIdx = roleIndices.get(roleKey) || 0;
    roleIndices.set(roleKey, roleIdx + 1);
    
    const original = originalMessages.find(
      (msg, i) => msg.role === anthroMsg.role && i >= roleIdx
    );
    
    // Convert content to parts
    const parts: Part[] = Array.isArray(anthroMsg.content)
      ? anthroMsg.content.map((block, i) => anthropicBlockToPart(block, `part_${idx}_${i}`))
      : [{ type: 'text', content: anthroMsg.content }];
    
    return {
      role: anthroMsg.role,
      parts,
      // Preserve original metadata if available
      ...(original && {
        timestamp: original.timestamp,
        sessionId: original.sessionId
      })
    };
  });
}

/**
 * Convert OpenCode Part to Anthropic content block
 */
function partToAnthropicBlock(part: Part): AnthropicContentBlock | null {
  if (part.type === 'text') {
    return {
      type: 'text',
      text: part.content || ''
    };
  }
  
  // Tool use (has input_data)
  if (part.type === 'tool_call' || (part.type === 'tool' && (part as any).input_data)) {
    const toolPart = part as any;
    return {
      type: 'tool_use',
      id: toolPart.id || 'tool_unknown',
      name: toolPart.tool_name || toolPart.tool || 'unknown',
      input: toolPart.input_data || {}
    };
  }
  
  // Tool result (has output_data)
  if (part.type === 'tool_result' || (part.type === 'tool' && (part as any).output_data)) {
    const resultPart = part as any;
    return {
      type: 'tool_result',
      tool_use_id: resultPart.tool_use_id || resultPart.id || 'tool_unknown',
      content: resultPart.output_data || resultPart.content || ''
    };
  }
  
  return null;
}

/**
 * Convert Anthropic content block to OpenCode Part
 */
function anthropicBlockToPart(block: AnthropicContentBlock, fallbackId: string): Part {
  if (block.type === 'text') {
    return {
      type: 'text',
      content: block.text || ''
    };
  }
  
  if (block.type === 'tool_use') {
    return {
      type: 'tool_call',
      tool_name: block.name || 'unknown',
      input_data: block.input || {},
      id: block.id || fallbackId
    } as any;
  }
  
  if (block.type === 'tool_result') {
    return {
      type: 'tool_result',
      output_data: block.content || '',
      tool_use_id: block.tool_use_id || fallbackId
    } as any;
  }
  
  return { type: 'text', content: '' };
}
