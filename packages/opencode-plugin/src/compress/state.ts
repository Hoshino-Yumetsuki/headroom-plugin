import type { SessionState } from '../types.ts';

export function createSessionState(): SessionState {
  return {
    sessionId: null,
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
