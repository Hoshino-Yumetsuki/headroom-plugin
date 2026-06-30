import type { Message, Part } from '@opencode-ai/sdk';

export interface MessageWithParts {
  info: Message;
  parts: Part[];
}

export interface HeadroomConfig {
  enabled: boolean;
  compress: {
    mode: 'range' | 'message';
    permission: 'allow' | 'ask' | 'deny';
    maxContextLimit: number;
    minContextLimit: number;
    nudgeFrequency: number;
    iterationNudgeThreshold: number;
    protectedTools: readonly string[];
    protectUserMessages: boolean;
  };
  strategies: {
    deduplication: { enabled: boolean };
    purgeErrors: { enabled: boolean; turns: number };
    staleContext: { enabled: boolean };
  };
  cli: {
    path: string;
    prescription: 'gentle' | 'standard' | 'aggressive';
  };
  protectedFilePatterns: readonly string[];
}

export interface SessionState {
  sessionId: string | null;
  compressionBlocks: CompressionBlock[];
  prunedPartIds: Set<string>;
  messageIdMap: Map<string, string>;
  shortIdMap: Map<string, string>;
  turnCount: number;
  fetchCount: number;
  lastUserMessageTurn: number;
  nudgeAnchor: number;
  toolCache: Map<string, ToolCacheEntry>;
  pendingManualCompress: boolean;
}

export interface CompressionBlock {
  id: string;
  startMessageId: string;
  endMessageId: string;
  summary: string;
  originalByteSize: number;
  compressedByteSize: number;
  messageCount: number;
  createdAt: number;
}

export interface ToolCacheEntry {
  signature: string;
  partId: string;
  messageId: string;
  turnIndex: number;
}

export interface DiagnoseResult {
  sessionId: string;
  totalBytes: number;
  totalParts: number;
  estimatedTokens: number;
  breakdown: Record<string, { bytes: number; count: number; pct: number }>;
  recommendations: readonly string[];
}

export interface TreatResult {
  sessionId: string;
  prescription: string;
  executed: boolean;
  bytesSaved: number;
  messagesPruned: number;
}

export interface StrategyRunResult {
  strategy: string;
  sessionId: string;
  executed: boolean;
  changes: number;
  bytesSaved: number;
}

export interface PriorityMap {
  low: string[];
  medium: string[];
  high: string[];
}

export interface Logger {
  debug(msg: string): void;
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

export type PruningStrategy = (
  messages: MessageWithParts[],
  state: SessionState,
  config: HeadroomConfig,
  logger: Logger
) => Promise<void>;
