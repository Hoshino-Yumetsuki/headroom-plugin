export function estimateTokenCount(text: string): number {
  return Math.ceil(text.length / 4);
}

export function calculateByteSize(obj: unknown): number {
  return new TextEncoder().encode(JSON.stringify(obj)).length;
}
