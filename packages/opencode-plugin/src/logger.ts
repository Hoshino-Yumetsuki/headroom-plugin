import { mkdirSync, appendFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import type { Logger, HeadroomConfig } from './types.ts';

/**
 * Creates a JSON-structured logger following headroom reverse proxy conventions:
 * - JSON format for machine parsing
 * - Local timezone timestamps
 * - Date-based file naming (YYYY-MM-DD.log)
 * - No automatic compression (rely on external logrotate)
 */
export function createLogger(config: HeadroomConfig): Logger {
  const logDir = config.log.path;
  mkdirSync(logDir, { recursive: true });

  function getLogFilePath(): string {
    const now = new Date();
    const pad = (n: number) => n.toString().padStart(2, '0');
    const dateStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    return join(logDir, `${dateStr}.log`);
  }

  function formatTimestamp(date: Date): string {
    const tzOffset = -date.getTimezoneOffset();
    const sign = tzOffset >= 0 ? '+' : '-';
    const pad = (n: number) => Math.floor(Math.abs(n)).toString().padStart(2, '0');
    const tzString = `${sign}${pad(tzOffset / 60)}:${pad(tzOffset % 60)}`;
    
    const year = date.getFullYear();
    const month = pad(date.getMonth() + 1);
    const day = pad(date.getDate());
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    const seconds = pad(date.getSeconds());
    const ms = date.getMilliseconds().toString().padStart(3, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}.${ms}${tzString}`;
  }

  function writeLog(level: string, msg: string, metadata?: Record<string, unknown>) {
    const now = new Date();
    const logEntry = {
      timestamp: formatTimestamp(now),
      level,
      message: msg,
      ...(metadata && { metadata })
    };
    
    const logPath = getLogFilePath();
    appendFileSync(logPath, JSON.stringify(logEntry) + '\n', 'utf-8');
  }

  return {
    debug(msg: string, metadata?: Record<string, unknown>): void {
      if (config.log.debug) {
        writeLog('DEBUG', msg, metadata);
      }
    },
    info(msg: string, metadata?: Record<string, unknown>): void {
      if (config.log.info) {
        writeLog('INFO', msg, metadata);
      }
    },
    warn(msg: string, metadata?: Record<string, unknown>): void {
      writeLog('WARN', msg, metadata);
    },
    error(msg: string, metadata?: Record<string, unknown>): void {
      writeLog('ERROR', msg, metadata);
    }
  };
}
