import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync } from 'node:fs';

const execFileAsync = promisify(execFile);

export async function findCli(configPath?: string): Promise<string | null> {
  if (configPath && existsSync(configPath)) {
    return configPath;
  }

  try {
    await execFileAsync('headroom-plugin-cli', ['--version']);
    return 'headroom-plugin-cli';
  } catch {
    // ignore
  }

  try {
    await execFileAsync('python', ['-m', 'headroom_cli', '--version']);
    return 'python';
  } catch {
    // ignore
  }

  return null;
}
