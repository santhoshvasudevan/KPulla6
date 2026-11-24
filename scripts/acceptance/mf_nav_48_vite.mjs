// Start Vite from this checkout's frontend/ with the proxy pointed at the acceptance backend.
// Usage (repo root): node scripts/acceptance/mf_nav_48_vite.mjs --backend http://127.0.0.1:18000 --port 15173
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const frontendDir = path.join(repoRoot, 'frontend');
const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
};
const backend = arg('--backend', 'http://127.0.0.1:18000');
const port = Number(arg('--port', '15173'));

const require = createRequire(path.join(frontendDir, 'package.json'));
const { createServer } = await import(pathToFileURL(require.resolve('vite')).href);
process.chdir(frontendDir);
const server = await createServer({
  root: frontendDir,
  configFile: path.join(frontendDir, 'vite.config.js'),
  server: {
    host: '127.0.0.1',
    port,
    strictPort: true,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/accounts': { target: backend, changeOrigin: true },
    },
  },
});
await server.listen();
console.log(JSON.stringify({ pid: process.pid, cwd: process.cwd(), port, backend }));
