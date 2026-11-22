import { test, expect } from '@playwright/test'
import { randomUUID } from 'node:crypto'

test('password confirmation, visibility and invalid fields protect private registration', async ({ page }) => {
  await page.goto('/register')
  const button = page.getByRole('button', { name: 'Create workspace', exact: true })
  await expect(button).toBeDisabled()
  await page.getByLabel('Business name').fill('Private registration test')
  await page.getByLabel('Username', { exact: true }).fill('private-' + randomUUID().slice(0, 8))
  await page.getByLabel('Email', { exact: true }).fill(randomUUID() + '@example.invalid')
  const password = page.getByLabel('Password', { exact: true })
  const confirmation = page.getByLabel('Confirm Password', { exact: true })
  await password.fill('Fixture!Garden5928')
  await confirmation.fill('Different!Garden5928')
  await expect(page.getByRole('alert')).toHaveText('Passwords do not match')
  await expect(button).toBeDisabled()
  await page.getByRole('button', { name: 'Show password', exact: true }).click()
  await expect(password).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Show confirm password', exact: true }).click()
  await expect(confirmation).toHaveAttribute('type', 'text')
  await confirmation.fill('Fixture!Garden5928')
  await expect(button).toBeEnabled()
  await button.click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
})

test('closed production registration explains portfolio status and directs to demo', async ({ page }) => {
  await page.route('**/api/v1/auth/session/', route => route.fulfill({ json: { user: null, public_demo: true, registration_enabled: false } }))
  await page.goto('/register')
  await expect(page.getByRole('heading', { name: 'Built for business. Open for exploration.' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create workspace', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Explore the fictional demo' })).toHaveAttribute('href', '/login')
})
