import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync } from 'node:fs';
import type { DiagnoseResult, TreatResult, StrategyRunResult } from '../types.ts';

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

export async function runDiagnose(
  sessionId: string,
  cliPath: string
): Promise<DiagnoseResult | null> {
  try {
    const args =
      cliPath === 'python'
        ? ['-m', 'headroom_cli', 'diagnose', sessionId, '--json']
        : ['diagnose', sessionId, '--json'];

    const { stdout } = await execFileAsync(cliPath, args);
    return JSON.parse(stdout) as DiagnoseResult;
  } catch {
    return null;
  }
}

export async function runTreat(
  sessionId: string,
  rx: string,
  execute: boolean,
  cliPath: string
): Promise<TreatResult | null> {
  try {
    const args =
      cliPath === 'python'
        ? ['-m', 'headroom_cli', 'treat', sessionId, '-rx', rx, '--json']
        : ['treat', sessionId, '-rx', rx, '--json'];

    if (execute) {
      args.push('--execute');
    }

    const { stdout } = await execFileAsync(cliPath, args);
    return JSON.parse(stdout) as TreatResult;
  } catch {
    return null;
  }
}

export async function runStrategy(
  name: string,
  sessionId: string,
  execute: boolean,
  cliPath: string
): Promise<StrategyRunResult | null> {
  try {
    const args =
      cliPath === 'python'
        ? ['-m', 'headroom_cli', 'strategy', name, sessionId, '--json']
        : ['strategy', name, sessionId, '--json'];

    if (execute) {
      args.push('--execute');
    }

    const { stdout } = await execFileAsync(cliPath, args);
    return JSON.parse(stdout) as StrategyRunResult;
  } catch {
    return null;
  }
}
