import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

test('public landing and mobile workspace support keyboard navigation and reduced motion', async ({ page }) => {
  test.setTimeout(90_000)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Know what sells/ })).toBeVisible()
  await expect(page.locator('.stock-sculpture')).toHaveCSS('animation-name', 'none')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
  await page.getByRole('link', { name: 'Create a workspace' }).click()
  const username = 'design-' + randomUUID().slice(0, 8)
  await page.getByLabel('Business name').fill('Design Acceptance Workspace')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Email').fill(username + '@example.invalid')
  await page.getByLabel('Password', { exact: true }).fill('Fixture!Wavelength459')
  if (await page.getByLabel('Confirm Password', { exact: true }).count()) await page.getByLabel('Confirm Password', { exact: true }).fill('Fixture!Wavelength459')
await page.getByRole('button', { name: 'Create workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()

  const menu = page.getByRole('button', { name: 'Open menu' })
  await menu.click()
  await expect(page.getByRole('button', { name: 'Close menu' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(menu).toBeFocused()

  for (const path of ['products', 'inventory', 'pos', 'purchases', 'sales', 'returns', 'suppliers',
    'customers', 'expenses', 'reports', 'insights', 'assistant', 'settings']) {
    await page.goto('/' + path)
    await expect(page.locator('#main-content h1').first()).toBeVisible()
    await expect(page.locator('#main-content [role="alert"]')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth), path).toBe(390)
  }
})
