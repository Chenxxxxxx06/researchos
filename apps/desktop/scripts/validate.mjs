import { access, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const configPath = path.join(root, 'src-tauri', 'tauri.conf.json');
const config = JSON.parse(await readFile(configPath, 'utf8'));
const pkg = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const releaseVersion = (await readFile(path.resolve(root, '..', '..', 'VERSION'), 'utf8')).trim();
const cargoManifest = await readFile(path.join(root, 'src-tauri', 'Cargo.toml'), 'utf8');
const cargoVersion = cargoManifest.match(/^version\s*=\s*"([^"]+)"/m)?.[1];

const errors = [];
if (config.productName !== 'ResearchOS') errors.push('productName must be ResearchOS');
if (config.version !== pkg.version) errors.push('package and Tauri versions must match');
if (releaseVersion !== pkg.version) errors.push('VERSION and desktop package versions must match');
if (cargoVersion !== pkg.version) errors.push('Cargo and desktop package versions must match');
if (!config.identifier?.startsWith('com.')) errors.push('bundle identifier must use reverse-DNS form');
if (config.app?.windows?.[0]?.minWidth < 1024) errors.push('desktop minimum width must support the research cockpit');
if (!config.bundle?.targets?.includes('msi') || !config.bundle?.targets?.includes('nsis')) errors.push('Windows MSI and NSIS targets are required');

const required = [
  'dist/index.html',
  'dist/styles.css',
  'dist/app.js',
  'dist/researchos-icon.png',
  'src-tauri/Cargo.toml',
  'src-tauri/src/main.rs',
  'src-tauri/src/lib.rs',
  'src-tauri/icons/32x32.png',
  'src-tauri/icons/128x128.png',
  'src-tauri/icons/128x128@2x.png',
  'src-tauri/icons/icon.ico',
];
for (const relative of required) {
  try {
    await access(path.join(root, relative));
  } catch {
    errors.push(`missing ${relative}`);
  }
}

if (errors.length) {
  console.error(errors.map((error) => `- ${error}`).join('\n'));
  process.exit(1);
}
console.log('ResearchOS Desktop source validation passed.');
