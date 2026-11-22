import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

test('insights prioritize real stock and compare recorded financial activity on desktop and mobile', async ({ page }, info) => {
  test.setTimeout(65_000)
  await page.setViewportSize({ width: 1440, height: 1020 })
  await page.goto('/register')
  const user = 'insights-' + randomUUID().slice(0, 8)
  await page.getByLabel('Business name').fill('Harbor Water Supply')
  await page.getByLabel('Username').fill(user)
  await page.getByLabel('Email').fill(user + '@example.invalid')
  await page.getByLabel('Password', { exact: true }).fill('Fixture!Wavelength459')
  if (await page.getByLabel('Confirm Password', { exact: true }).count()) await page.getByLabel('Confirm Password', { exact: true }).fill('Fixture!Wavelength459')
await page.getByRole('button', { name: 'Create workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()

  const [business] = await (await page.request.get('/api/v1/businesses/')).json()
  const token = (await page.context().cookies()).find(cookie => cookie.name === 'csrftoken')!
  const endpoint = '/api/v1/businesses/' + business.id + '/'
  async function seed(resource: string, data: object) {
    const response = await page.request.post(endpoint + resource, { data, headers: { 'X-CSRFToken': token.value } })
    expect(response.ok()).toBe(true)
    return response.json()
  }
  const water = await seed('products/', { name: 'Bottled Water (75cl)', sku: 'WATER-75', price: '250', reorder_level: '10' })
  await seed('movements/', { product: water.id, quantity: '8', unit_cost: '150' })
  await seed('products/', { name: 'Sparkling Water (50cl)', sku: 'SPARK-50', price: '400', reorder_level: '5' })
  const customer = await seed('customers/', { name: 'Harbor Café' })
  await seed('sales/checkout/', { request_id: randomUUID(), customer: customer.id, lines: [{ product: water.id, quantity: '4' }],
    expected_total: '1000', payments: [{ method: 'cash', amount: '250' }] })
  const category = await seed('expense-categories/', { name: 'Transport' })
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: business.timezone }).format(new Date())
  const dateAgo = (days: number) => new Date(Date.parse(today) - days * 86400000).toISOString().slice(0, 10)
  for (const offset of [1, 2, 3, 6]) {
    await seed('expenses/', { category: category.id, amount: offset === 1 ? '400' : '100', incurred_on: dateAgo(offset),
      description: 'Recorded delivery cost', method: 'cash' })
  }

  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Business Insights' })).toBeVisible()
  await page.getByLabel('From', { exact: true }).fill(dateAgo(1))
  await page.getByLabel('Through', { exact: true }).fill(today)
  await page.getByLabel('Compare with').selectOption('custom')
  await page.getByLabel('Comparison from').fill(dateAgo(8))
  await page.getByLabel('Comparison through').fill(dateAgo(2))
  await page.getByRole('button', { name: 'Apply dates' }).click()
  await expect(page.getByText('Check an unusual Transport expense')).toBeVisible()
  await expect(page.getByText('Review stock for Sparkling Water (50cl)')).toBeVisible()
  await expect(page.getByText('A forecast needs eight complete weeks', { exact: false })).toBeVisible()
  await page.screenshot({ path: info.outputPath('phase5-insights-priorities.png'), fullPage: true })

  await page.getByRole('button', { name: 'Payments', exact: true }).click()
  await expect(page.getByRole('table', { name: 'Customer payment activity' }).getByRole('row', { name: /Harbor Café/ })).toContainText('₦750.00')
  await page.getByRole('button', { name: 'Performance', exact: true }).click()
  const productTable = page.getByRole('table', { name: 'Product performance' })
  await expect(productTable).toContainText('₦1,000.00')
  await expect(productTable).toContainText('₦400.00')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  await page.screenshot({ path: info.outputPath('phase5-insights-mobile.png'), fullPage: true })
  await page.getByRole('link', { name: 'Discuss this comparison' }).click()
  const composer = page.getByRole('textbox', { name: 'Message StockPilot AI' })
  await expect(composer).toHaveValue(new RegExp(dateAgo(8)))
  await composer.press('Enter')
  await expect(page.getByRole('heading', { name: 'What moved operating profit' })).toBeVisible()
  await expect(page.getByRole('row', { name: /Gross sales movement/ })).toContainText('₦1,000.00')
  await composer.fill('What about yesterday?')
  await composer.press('Enter')
  await expect(page.getByRole('heading', { name: 'What moved operating profit' })).toHaveCount(2)
  await expect(page.getByRole('row', { name: /Gross sales movement/ }).last()).toContainText('₦0.00')
})
