import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './showcase-tests', workers: 1, timeout: 60_000,
  outputDir: './showcase-test-results', expect: { timeout: 15_000 },
  use: { baseURL: 'http://127.0.0.1:5198', channel: 'msedge', trace: 'retain-on-failure' },
  webServer: { command: 'node preview-showcase.mjs', url: 'http://127.0.0.1:5198', reuseExistingServer: false },
})
