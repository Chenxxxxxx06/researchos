import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 2,
  workers: 1,
  timeout: 30000,
  reporter: [['list'], ['html', { outputFolder: '../../artifacts/playwright-report' }]],
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'on',
    video: 'off',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  outputDir: '../../artifacts/screenshots',
});
