import { test, expect } from '@playwright/test'

test('stalled sign-in stops working state and offers a clear retry message', async ({ page }) => {
  await page.clock.install()
  await page.goto('/login')
  await page.route('**/api/v1/auth/login/', () => new Promise(() => {}))
  await page.getByLabel('Username', { exact: true }).fill('timeout-fixture')
  await page.getByLabel('Password', { exact: true }).fill('FixturePassword459!')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Working…' })).toBeVisible()
  await page.clock.fastForward(31_000)
  await expect(page.getByRole('alert')).toContainText('Sign-in took too long')
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled()
})

test('hosting warm-up HTML is reported as unavailable instead of a successful login', async ({ page }) => {
  await page.goto('/login')
  await page.route('**/api/v1/auth/login/', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<p>Starting service</p>' }))
  await page.getByLabel('Username', { exact: true }).fill('timeout-fixture')
  await page.getByLabel('Password', { exact: true }).fill('FixturePassword459!')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('server is waking up')
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled()
})
