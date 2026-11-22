import { test, expect } from '@playwright/test'

test('public registration remains closed with demo entry and responsive explanation', async ({ page, context, baseURL }) => {
  await page.goto('/register')
  await expect(page.getByRole('heading', { name: 'Built for business. Open for exploration.' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create workspace', exact: true })).toHaveCount(0)
  const session = await (await context.request.get('/api/v1/auth/session/')).json()
  expect(session.registration_enabled).toBe(false)
  const csrf = (await context.cookies()).find(cookie => cookie.name === 'csrftoken')!.value
  const denied = await context.request.post('/api/v1/auth/register/', {
    headers: { 'X-CSRFToken': csrf, Origin: baseURL! }, data: {},
  })
  expect(denied.status()).toBe(403)
  expect((await denied.json()).detail).toContain('registration is currently closed')
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 950 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: `../docs/screenshots/phase9-registration-${width}.png`, fullPage: true })
  }
  await page.getByRole('button', { name: 'Enter fictional demo' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
})
