import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import type { HeadroomConfig } from './types.ts';
import type { PluginInput } from '@opencode-ai/plugin';

const DEFAULT_CONFIG: HeadroomConfig = {
  enabled: true,
  compress: {
    mode: 'range',
    permission: 'allow',
    maxContextLimit: 100000,
    minContextLimit: 50000,
    nudgeFrequency: 5,
    iterationNudgeThreshold: 15,
    protectedTools: ['task', 'skill', 'todowrite', 'todoread'],
    protectUserMessages: false
  },
  strategies: {
    deduplication: { enabled: true },
    purgeErrors: { enabled: true, turns: 4 },
    staleContext: { enabled: true }
  },
  cli: {
    path: 'headroom-cli',
    prescription: 'gentle'
  },
  protectedFilePatterns: []
};

function stripJsoncComments(content: string): string {
  let result = '';
  let inString = false;
  let inSingleLineComment = false;
  let inMultiLineComment = false;
  let escapeNext = false;

  for (let i = 0; i < content.length; i++) {
    const char = content[i];
    const nextChar = content[i + 1];

    if (escapeNext) {
      escapeNext = false;
      if (!inSingleLineComment && !inMultiLineComment) {
        result += char;
      }
      continue;
    }

    if (char === '\\' && inString) {
      escapeNext = true;
      result += char;
      continue;
    }

    if (char === '"' && !inSingleLineComment && !inMultiLineComment) {
      inString = !inString;
      result += char;
      continue;
    }

    if (!inString) {
      if (char === '/' && nextChar === '/' && !inMultiLineComment) {
        inSingleLineComment = true;
        i++;
        continue;
      }

      if (char === '/' && nextChar === '*' && !inSingleLineComment) {
        inMultiLineComment = true;
        i++;
        continue;
      }

      if (char === '\n' && inSingleLineComment) {
        inSingleLineComment = false;
        result += char;
        continue;
      }

      if (char === '*' && nextChar === '/' && inMultiLineComment) {
        inMultiLineComment = false;
        i++;
        continue;
      }
    }

    if (!inSingleLineComment && !inMultiLineComment) {
      result += char;
    }
  }

  return result.replace(/,(\s*[}\]])/g, '$1');
}

function loadConfigFile(path: string): Partial<HeadroomConfig> | null {
  if (!existsSync(path)) return null;

  try {
    const content = readFileSync(path, 'utf-8');
    const stripped = stripJsoncComments(content);
    return JSON.parse(stripped) as Partial<HeadroomConfig>;
  } catch {
    return null;
  }
}

function mergeConfig(base: HeadroomConfig, override: Partial<HeadroomConfig>): HeadroomConfig {
  return {
    enabled: override.enabled ?? base.enabled,
    compress: {
      mode: override.compress?.mode ?? base.compress.mode,
      permission: override.compress?.permission ?? base.compress.permission,
      maxContextLimit: override.compress?.maxContextLimit ?? base.compress.maxContextLimit,
      minContextLimit: override.compress?.minContextLimit ?? base.compress.minContextLimit,
      nudgeFrequency: override.compress?.nudgeFrequency ?? base.compress.nudgeFrequency,
      iterationNudgeThreshold:
        override.compress?.iterationNudgeThreshold ?? base.compress.iterationNudgeThreshold,
      protectedTools: override.compress?.protectedTools ?? base.compress.protectedTools,
      protectUserMessages:
        override.compress?.protectUserMessages ?? base.compress.protectUserMessages
    },
    strategies: {
      deduplication: {
        enabled:
          override.strategies?.deduplication?.enabled ?? base.strategies.deduplication.enabled
      },
      purgeErrors: {
        enabled: override.strategies?.purgeErrors?.enabled ?? base.strategies.purgeErrors.enabled,
        turns: override.strategies?.purgeErrors?.turns ?? base.strategies.purgeErrors.turns
      },
      staleContext: {
        enabled: override.strategies?.staleContext?.enabled ?? base.strategies.staleContext.enabled
      }
    },
    cli: {
      path: override.cli?.path ?? base.cli.path,
      prescription: override.cli?.prescription ?? base.cli.prescription
    },
    protectedFilePatterns: override.protectedFilePatterns ?? base.protectedFilePatterns
  };
}

export function loadConfig(ctx: PluginInput): HeadroomConfig {
  let config = { ...DEFAULT_CONFIG };

  const globalPath = join(homedir(), '.config', 'opencode', 'headroom.jsonc');
  const globalConfig = loadConfigFile(globalPath);
  if (globalConfig) {
    config = mergeConfig(config, globalConfig);
  }

  const projectPath = join(ctx.directory, '.opencode', 'headroom.jsonc');
  const projectConfig = loadConfigFile(projectPath);
  if (projectConfig) {
    config = mergeConfig(config, projectConfig);
  }

  return config;
}
