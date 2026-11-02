import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const distDir = path.join(rootDir, 'dist');

console.log('🏗️  Compilazione distribuzione statica per ppatos.pagine.ch...');

if (fs.existsSync(distDir)) {
  fs.rmSync(distDir, { recursive: true, force: true });
}
fs.mkdirSync(distDir, { recursive: true });

function copyFileSafe(srcRel, destRel) {
  const src = path.join(rootDir, srcRel);
  const dest = path.join(distDir, destRel);
  if (fs.existsSync(src)) {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
  }
}

// File statici
copyFileSafe('index.html', 'index.html');
copyFileSafe('pch.json', 'pch.json');

console.log('✅ Distribuzione statica PPaToS generata in dist/');
