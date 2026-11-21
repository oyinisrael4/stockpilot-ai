// Loopback-only verification server; applies the Cloudflare static security policy.
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('./dist-showcase/', import.meta.url))
const headers = Object.fromEntries(fs.readFileSync(path.join(root, '_headers'), 'utf8').split('\n').filter(line => line.includes(':')).map(line => {
  const colon = line.indexOf(':'); return [line.slice(0, colon).trim(), line.slice(colon + 1).trim()]
}))
http.createServer((request, response) => {
  let pathname
  try { pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname) } catch { response.writeHead(400); response.end(); return }
  if (pathname.startsWith('/stockpilot/')) pathname = pathname.slice('/stockpilot'.length)
  if (pathname.endsWith('/')) pathname += 'index.html'
  const target = path.resolve(root, '.' + pathname)
  if (!target.startsWith(root) || !fs.existsSync(target) || !fs.statSync(target).isFile()) { response.writeHead(404, headers); response.end('Not found'); return }
  const body = fs.readFileSync(target)
  response.writeHead(200, { ...headers, 'Content-Length': body.length, 'Content-Type': ({ '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.webp': 'image/webp' })[path.extname(target)] || 'text/plain' })
  response.end(body)
}).listen(5198, '127.0.0.1', () => console.log('Static verification server on loopback port 5198'))
