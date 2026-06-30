/**
 * Test if we can read the generated JSON
 */

import fs from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const tempFile = join(tmpdir(), 'headroom-request.json');

console.log('Reading:', tempFile);

try {
  const content = fs.readFileSync(tempFile, 'utf-8');
  console.log('File size:', content.length);

  // Try to parse
  const parsed = JSON.parse(content);
  console.log('✅ JSON is valid!');
  console.log('Message count:', parsed.messages?.length);

  // Check character 51272
  const around = content.substring(51260, 51285);
  console.log('\nAround character 51272:');
  console.log(around);
  console.log('\nChar codes:');
  for (let i = 0; i < around.length; i++) {
    console.log(`${51260 + i}: '${around[i]}' (${around.charCodeAt(i)})`);
  }
} catch (e) {
  console.error('❌ Error:', e.message);

  // Read raw content around error position
  try {
    const content = fs.readFileSync(tempFile, 'utf-8');
    const around = content.substring(51260, 51285);
    console.log('\nAround character 51272:');
    console.log(around);
    console.log('\nChar codes:');
    for (let i = 0; i < around.length; i++) {
      console.log(`${51260 + i}: '${around[i]}' (${around.charCodeAt(i)})`);
    }
  } catch (err) {
    console.error('Cannot read file:', err.message);
  }
}
