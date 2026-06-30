import { mkdirSync, appendFileSync, existsSync, statSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { exec } from 'node:child_process';
import type { Logger, HeadroomConfig } from './types.ts';

export function createLogger(config: HeadroomConfig): Logger {
  const logDir = config.log.path;
  mkdirSync(logDir, { recursive: true });

  function getLogFileName(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `headroom-${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}.log`;
  }

  function rotateAndCompress(currentPath: string, date: Date) {
    if (!existsSync(currentPath)) return;
    
    // Check if the file is from a previous day
    const stats = statSync(currentPath);
    const fileDate = new Date(stats.mtime);
    
    if (fileDate.getDate() !== date.getDate() || 
        fileDate.getMonth() !== date.getMonth() || 
        fileDate.getFullYear() !== date.getFullYear()) {
      
      const oldFileName = getLogFileName(fileDate);
      const oldFilePath = join(logDir, oldFileName);
      
      renameSync(currentPath, oldFilePath);
      
      // Compress the old file in the background (platform-independent fallback)
      exec(`gzip "${oldFilePath}"`, (err) => {
        if (err) {
            // Fallback for Windows if gzip is not available, try to use tar
            exec(`tar -czf "${oldFilePath}.gz" "${oldFilePath}" && del "${oldFilePath}"`, (err2) => {
                 if (err2) {
                     // If both fail, we just leave the uncompressed file.
                     console.error(`Failed to compress log file: ${err2.message}`);
                 }
            });
        }
      });
    }
  }

  function writeLog(level: string, msg: string) {
    const now = new Date();
    rotateAndCompress(join(logDir, 'headroom.log'), now);
    
    const currentPath = join(logDir, 'headroom.log');
    
    // Get local timezone offset
    const tzOffset = -now.getTimezoneOffset();
    const sign = tzOffset >= 0 ? '+' : '-';
    const pad = (n: number) => Math.floor(Math.abs(n)).toString().padStart(2, '0');
    const tzString = `${sign}${pad(tzOffset / 60)}:${pad(tzOffset % 60)}`;
    
    // YYYY-MM-DD HH:mm:ss.SSS +Z
    const timestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}.${now.getMilliseconds().toString().padStart(3, '0')} ${tzString}`;

    appendFileSync(currentPath, `[${timestamp}] ${level}: ${msg}\n`, 'utf-8');
  }

  return {
    debug(msg: string): void {
      if (config.log.debug) {
        writeLog('DEBUG', msg);
      }
    },
    info(msg: string): void {
      if (config.log.info) {
        writeLog('INFO', msg);
      }
    },
    warn(msg: string): void {
      writeLog('WARN', msg);
    },
    error(msg: string): void {
      writeLog('ERROR', msg);
    }
  };
}
