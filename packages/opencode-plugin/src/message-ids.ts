import type { MessageWithParts } from './types.ts';

/**
 * Assigns short sequential IDs to messages for internal tracking only.
 * These IDs are NOT injected into message content (transparency principle).
 */
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

/**
 * No-op function maintained for backward compatibility.
 * Headroom plugin follows the transparency principle of the reverse proxy:
 * no metadata is injected into messages visible to the model or user.
 */
export function injectMessageIdTags(
  _messages: MessageWithParts[],
  _idMap: Map<string, string>
): void {
  // Intentionally empty - IDs are for internal tracking only
}

/**
 * No-op function maintained for backward compatibility.
 * No metadata injection means no cleanup needed.
 */
export function stripModelGeneratedMetadata(_messages: MessageWithParts[]): void {
  // Intentionally empty - no metadata to strip
}
