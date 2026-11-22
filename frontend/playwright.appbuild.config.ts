import { defineConfig } from '@playwright/test'
import process from 'node:process'
import original from './playwright.config'
const python = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'
const origin = 'http://127.0.0.1:8812'
export default defineConfig({
  ...original, outputDir: './appbuild-test-results', use: { ...original.use, baseURL: origin },
  webServer: {
    command: `"${python}" backend/manage.py runserver 127.0.0.1:8812 --noreload`, cwd: '..', url: origin + '/api/v1/live/',
    env: { PGDATABASE: 'stockpilot_browser', DATABASE_URL: '', DJANGO_TRUSTED_ORIGINS: origin,
      STOCKPILOT_SERVE_FRONTEND: '1', STOCKPILOT_AI_PROVIDER: 'openai', STOCKPILOT_AI_MODEL: '',
      STOCKPILOT_AI_API_KEY: '', STOCKPILOT_VOICE_PROVIDER: 'offline', STOCKPILOT_PUBLIC_DEMO: '0' },
  },
})
