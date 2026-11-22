import { defineConfig } from '@playwright/test'
import process from 'node:process'
const origin = process.env.STOCKPILOT_HOSTED_URL || ''
if (!/^https:\/\/[a-z0-9-]+\.onrender\.com\/?$/.test(origin)) throw new Error('Set STOCKPILOT_HOSTED_URL to the verified Render HTTPS origin, without credentials.')
export default defineConfig({
  testDir: './hosted-tests', workers: 1, timeout: 300_000, retries: 0, outputDir: './hosted-test-results',
  expect: { timeout: 80_000 },
  use: { baseURL: origin, channel: 'msedge', trace: 'off', launchOptions: process.env.STOCKPILOT_VOICE_WAV ? { args: [
    '--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + process.env.STOCKPILOT_VOICE_WAV,
  ] } : undefined },
})
