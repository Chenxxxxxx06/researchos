import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * Unit tests only (pure DOM-free modules; node environment). Playwright specs
 * under e2e/ are excluded — they run via `pnpm test:e2e`.
 */
export default defineConfig({
  resolve: {
    alias: { '@': rootDir },
  },
  test: {
    environment: 'node',
    include: ['lib/**/*.test.ts', 'components/**/*.test.ts'],
  },
});
