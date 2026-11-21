import { defineConfig } from '@playwright/test'
import process from 'node:process'

const python = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'

const frontendPort = process.env.STOCKPILOT_TEST_FRONTEND_PORT ?? '5174'
const backendPort = process.env.STOCKPILOT_TEST_BACKEND_PORT ?? '8001'
const frontendOrigin = `http://127.0.0.1:${frontendPort}`
const backendOrigin = `http://127.0.0.1:${backendPort}`

export default defineConfig({
  testDir: './tests',
  workers: 1,
  expect: { timeout: 12_000 },
  use: {
    baseURL: frontendOrigin,
    channel: process.env.STOCKPILOT_BROWSER || undefined,
    trace: 'retain-on-failure',
    launchOptions: process.env.STOCKPILOT_VOICE_WAV ? { args: [
      '--use-fake-device-for-media-stream',
      '--use-file-for-fake-audio-capture=' + process.env.STOCKPILOT_VOICE_WAV,
    ] } : undefined,
  },
  webServer: [
    {
      command: `"${python}" backend/manage.py runserver 127.0.0.1:${backendPort} --noreload`,
      cwd: '..',
      env: {
        PGDATABASE: 'stockpilot_browser',
        DJANGO_TRUSTED_ORIGINS: frontendOrigin,
        STOCKPILOT_AI_API_KEY: '',
        STOCKPILOT_AI_PROVIDER: 'openai',
        STOCKPILOT_AI_MODEL: '',
      },
      url: backendOrigin + '/api/v1/health/',
    },
    {
      command: `npm run dev -- --port ${frontendPort} --strictPort`,
      env: { STOCKPILOT_API_ORIGIN: backendOrigin },
      url: frontendOrigin + '/',
    },
  ],
})
