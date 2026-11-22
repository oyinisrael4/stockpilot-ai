import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import process from 'node:process'

test('real hosted Groq conversation, speech, confirmation and persisted Neon records', async ({ page, context, baseURL }) => {
  if (!process.env.STOCKPILOT_VOICE_WAV) throw new Error('Provide the private local audio verification fixture path; never commit recordings.')
  await page.goto('/login')
  await page.getByRole('button', { name: 'Enter fictional demo' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  const cookies = await context.cookies()
  expect(cookies.find(c => c.name === 'sessionid')?.secure).toBeTruthy()
  const csrf = cookies.find(c => c.name === 'csrftoken')!.value
  const headers = { 'X-CSRFToken': csrf, Origin: baseURL! }
  const businesses = await (await context.request.get('/api/v1/businesses/')).json()
  const business = businesses.find((b: { name: string }) => b.name === 'Juniper Market Supply · Demo')
  expect(business).toBeTruthy()
  const root = `/api/v1/businesses/${business.id}/`
  const status = await (await context.request.get(root + 'assistant/status/')).json()
  expect(status).toMatchObject({ provider_enabled: true, provider: 'groq', voice_provider: 'groq' })
  const create = await context.request.post(root + 'assistant/conversations/', { headers })
  expect(create.status()).toBe(201)
  const conversation = await create.json()
  async function message(text: string) {
    const response = await context.request.post(root + `assistant/conversations/${conversation.id}/messages/`, {
      headers, data: { text, request_id: crypto.randomUUID() }, timeout: 55_000,
    })
    expect(response.status()).toBe(201)
    const result = await response.json()
    expect(result.answer.mode).toBe('provider')
    return result
  }
  const products = await (await context.request.get(root + 'products/?search=WATER-75')).json()
  const product = products.results.find((p: { sku: string }) => p.sku === 'WATER-75')
  expect(Number(product.stock)).toBeGreaterThanOrEqual(2)
  const sale = await message('Please sell two WATER-75 in cash.')
  expect(sale.proposal?.status).toBe('pending')
  const confirmURL = root + `assistant/proposals/${sale.proposal.id}/confirm/`
  const posted = await context.request.post(confirmURL, { headers, data: { revision: sale.proposal.revision } })
  expect(posted.status()).toBe(200)
  const again = await context.request.post(confirmURL, { headers, data: { revision: sale.proposal.revision } })
  expect(again.status()).toBe(200)
  expect((await again.json()).proposal.result).toEqual((await posted.json()).proposal.result)
  const after = await (await context.request.get(root + `products/${product.id}/`)).json()
  expect(Number(after.stock)).toBe(Number(product.stock) - 2)
  // Separate messages by 31s: stay below the shared two-requests/minute application allowance.
  await page.waitForTimeout(31_000)
  expect((await message('How much gross profit did we make this month?')).proposal).toBeNull()
  await page.waitForTimeout(31_000)
  const followup = await message('What about last month?')
  expect(followup.proposal).toBeNull()
  const transcription = await context.request.post(root + 'assistant/transcribe/', {
    headers: { ...headers, 'Content-Type': 'audio/wav' }, data: fs.readFileSync(process.env.STOCKPILOT_VOICE_WAV), timeout: 55_000,
  })
  expect(transcription.status()).toBe(200)
  expect((await transcription.json()).text.toLowerCase()).toContain('water')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  const persisted = await (await context.request.get(root + `products/${product.id}/`)).json()
  expect(persisted.stock).toBe(after.stock)
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 950 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: `../docs/screenshots/hosted-overview-${width}.png`, fullPage: true })
  }
})
