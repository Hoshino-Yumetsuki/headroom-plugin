import type { MessageWithParts } from './types.ts';
import type { Part } from '@opencode-ai/sdk';

export function assignMessageIds(messages: readonly MessageWithParts[]): Map<string, string> {
  const map = new Map<string, string>();
  let counter = 1;
  for (const msg of messages) {
    const shortId = `m${String(counter).padStart(4, '0')}`;
    map.set(msg.info.id, shortId);
    counter++;
  }
  return map;
}

export function injectMessageIdTags(
  messages: MessageWithParts[],
  idMap: Map<string, string>
): void {
  for (const msg of messages) {
    const shortId = idMap.get(msg.info.id);
    if (!shortId) continue;

    // Create a fake ToolPart that will render as [headroom] m0001 in the UI
    const fakeToolPart: Part = {
      id: `headroom-${shortId}`,
      sessionID: msg.info.sessionID,
      messageID: msg.info.id,
      type: 'tool',
      callID: `headroom-${shortId}`,
      tool: 'headroom',
      state: {
        status: 'completed',
        input: {},
        output: shortId,
        time: {
          start: Date.now(),
          end: Date.now()
        }
      },
      metadata: {
        headroomId: shortId,
        silent: true
      }
    };

    // Insert the fake tool part at the beginning
    msg.parts.unshift(fakeToolPart as any);
  }
}

export function stripModelGeneratedMetadata(messages: MessageWithParts[]): void {
  for (const msg of messages) {
    if (msg.info.role !== 'assistant') continue;

    // Remove any fake headroom tool parts that the model might have generated
    msg.parts = msg.parts.filter(part => {
      if (part.type === 'tool' && part.tool === 'headroom') {
        return false;
      }
      return true;
    });
  }
}
