import { mkdirSync, appendFileSync, existsSync, readdirSync, statSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { exec } from 'node:child_process';
import type { Logger, HeadroomConfig } from './types.ts';

/**
 * Creates a JSON-structured logger following headroom reverse proxy conventions:
 * - JSON format for machine parsing
 * - Local timezone timestamps
 * - Date-based file naming (YYYY-MM-DD.log)
 * - Automatic gzip compression of rotated logs
 */
export function createLogger(config: HeadroomConfig): Logger {
  const logDir = config.log.path;
  mkdirSync(logDir, { recursive: true });

  function getLogFilePath(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, '0');
    const dateStr = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
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

  function compressOldLogs() {
    if (!existsSync(logDir)) return;

    const today = new Date();
    const todayPath = getLogFilePath(today);

    try {
      const files = readdirSync(logDir);
      
      for (const file of files) {
        // Only compress .log files that are not today's log
        if (!file.endsWith('.log')) continue;
        
        const filePath = join(logDir, file);
        
        // Skip today's log file
        if (filePath === todayPath) continue;

        // Check if file is from a previous day
        const stats = statSync(filePath);
        const fileDate = new Date(stats.mtime);
        
        if (
          fileDate.getDate() !== today.getDate() ||
          fileDate.getMonth() !== today.getMonth() ||
          fileDate.getFullYear() !== today.getFullYear()
        ) {
          // Compress in background
          exec(`gzip "${filePath}"`, (err) => {
            if (err) {
              // Fallback for Windows if gzip is not available
              exec(`powershell -Command "Compress-Archive -Path '${filePath}' -DestinationPath '${filePath}.zip' -Force; Remove-Item '${filePath}'"`, (err2) => {
                if (err2) {
                  // If both fail, leave uncompressed (silent failure)
                }
              });
            }
          });
        }
      }
    } catch {
      // Silent failure - don't block logging if compression fails
    }
  }

  function writeLog(level: string, msg: string, metadata?: Record<string, unknown>) {
    const now = new Date();
    const logEntry = {
      timestamp: formatTimestamp(now),
      level,
      message: msg,
      ...(metadata && { metadata })
    };
    
    const logPath = getLogFilePath(now);
    
    // Compress old logs on first write of the day
    if (!existsSync(logPath)) {
      compressOldLogs();
    }
    
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
