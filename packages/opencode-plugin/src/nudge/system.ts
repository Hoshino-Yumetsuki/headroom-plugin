import type { HeadroomConfig, SessionState } from '../types.ts';

export function createSystemPromptHandler(config: HeadroomConfig, _state: SessionState) {
  return async (input: unknown, output: { system: string[] }) => {
    if (!config.enabled) return;

    const prompt = `
<context-management>
You have access to a "compress" tool for managing conversation context.
When the conversation grows long, use compress to summarize older message ranges.
Specify startId and endId using the <headroom-id> tags visible in messages.
Write concise summaries that preserve: key decisions, file paths modified,
error resolutions, and current task state.

Example usage:
- Review the conversation and identify completed phases
- Note the headroom-id tags (e.g., m0001, m0050)
- Call compress with a range and a summary of key outcomes

This helps maintain context window efficiency while preserving critical information.
</context-management>`;

    const lastIndex = output.system.length - 1;
    if (lastIndex >= 0 && output.system[lastIndex] !== undefined) {
      output.system[lastIndex] += '\n\n' + prompt;
    } else {
      output.system.push(prompt);
    }
  };
}
