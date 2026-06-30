import { defineConfig } from 'rolldown';
import pkg from './package.json' with { type: 'json' };
import { dts } from 'rolldown-plugin-dts';

const external = new RegExp(
  `^(node:|${[
    ...Object.getOwnPropertyNames(pkg.peerDependencies ?? {}),
    ...Object.getOwnPropertyNames(pkg.devDependencies ?? {})
  ].join('|')})`
);

export default defineConfig([
  {
    input: './src/index.ts',
    output: [{ file: 'lib/index.mjs', format: 'es' }],
    external
  },
  {
    input: './src/index.ts',
    output: [{ dir: 'lib', format: 'es' }],
    plugins: [dts({ emitDtsOnly: true })],
    external
  }
]);
