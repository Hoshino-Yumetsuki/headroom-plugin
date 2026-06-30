import type { SessionState } from '../types.ts';
import { randomUUID } from 'node:crypto';

export function createSessionState(): SessionState {
  return {
    sessionId: null,
    requestId: randomUUID(), // Generate UUID v4 for request tracking
    compressionBlocks: [],
    prunedPartIds: new Set(),
    messageIdMap: new Map(),
    shortIdMap: new Map(),
    turnCount: 0,
    fetchCount: 0,
    lastUserMessageTurn: 0,
    nudgeAnchor: 0,
    toolCache: new Map(),
    pendingManualCompress: false,
    totalBytesSaved: 0,
    lastToastMilestone: 0
  };
}

export function resetSessionState(state: SessionState): void {
  state.sessionId = null;
  state.requestId = randomUUID(); // Generate new request ID on reset
  state.compressionBlocks = [];
  state.prunedPartIds.clear();
  state.messageIdMap.clear();
  state.shortIdMap.clear();
  state.turnCount = 0;
  state.fetchCount = 0;
  state.lastUserMessageTurn = 0;
  state.nudgeAnchor = 0;
  state.toolCache.clear();
  state.pendingManualCompress = false;
  state.totalBytesSaved = 0;
  state.lastToastMilestone = 0;
}
