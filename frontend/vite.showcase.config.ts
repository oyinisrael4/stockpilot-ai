import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { readFileSync } from 'node:fs'
export default defineConfig({
  root: 'showcase', base: './', publicDir: '../public', plugins: [react(), {
    name: 'showcase-security-headers',
    generateBundle() { this.emitFile({ type: 'asset', fileName: '_headers', source: readFileSync(new URL('./showcase/_headers', import.meta.url), 'utf8') }) },
  }],
  envDir: 'showcase',
  build: { outDir: '../dist-showcase', emptyOutDir: true, sourcemap: false },
  preview: { host: '127.0.0.1', port: 5198, strictPort: true },
})
