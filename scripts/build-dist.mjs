import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

console.log('🏗️  Compilazione distribuzione PPaToS.ch con design autentico...');
execSync('py scripts/render_dist.py', { cwd: rootDir, stdio: 'inherit' });
console.log('✅ Build PPaToS completata con successo!');
