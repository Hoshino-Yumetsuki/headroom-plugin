import { mkdirSync, appendFileSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import type { Logger } from './types.ts';

export function createLogger(): Logger {
  const logDir = join(homedir(), '.config', 'opencode', 'logs', 'headroom');
  mkdirSync(logDir, { recursive: true });

  const debugPath = join(logDir, 'debug.log');
  const infoPath = join(logDir, 'headroom.log');

  function timestamp(): string {
    return new Date().toISOString();
  }

  return {
    debug(msg: string): void {
      appendFileSync(debugPath, `[${timestamp()}] DEBUG: ${msg}\n`, 'utf-8');
    },
    info(msg: string): void {
      appendFileSync(infoPath, `[${timestamp()}] INFO: ${msg}\n`, 'utf-8');
    },
    warn(msg: string): void {
      appendFileSync(infoPath, `[${timestamp()}] WARN: ${msg}\n`, 'utf-8');
    },
    error(msg: string): void {
      appendFileSync(infoPath, `[${timestamp()}] ERROR: ${msg}\n`, 'utf-8');
    }
  };
}
