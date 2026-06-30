import type { MessageWithParts } from './types.ts';

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

    const firstTextPartIndex = msg.parts.findIndex((p) => p.type === 'text');
    if (firstTextPartIndex === -1) continue;

    const firstTextPart = msg.parts[firstTextPartIndex];
    if (firstTextPart?.type !== 'text') continue;

    const tag = `<headroom-id>${shortId}</headroom-id>\n\n`;
    firstTextPart.text = tag + firstTextPart.text;
  }
}

export function stripModelGeneratedMetadata(messages: MessageWithParts[]): void {
  for (const msg of messages) {
    if (msg.info.role !== 'assistant') continue;

    for (const part of msg.parts) {
      if (part.type !== 'text') continue;

      part.text = part.text.replace(/<headroom-id>.*?<\/headroom-id>\s*/g, '');
    }
  }
}
