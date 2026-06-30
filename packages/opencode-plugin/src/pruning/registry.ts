import type { PruningStrategy } from '../types.ts';

const strategies = new Map<string, PruningStrategy>();

export function registerStrategy(name: string, strategy: PruningStrategy): void {
  strategies.set(name, strategy);
}

export function getStrategy(name: string): PruningStrategy | undefined {
  return strategies.get(name);
}

export function getAllStrategies(): Map<string, PruningStrategy> {
  return strategies;
}
