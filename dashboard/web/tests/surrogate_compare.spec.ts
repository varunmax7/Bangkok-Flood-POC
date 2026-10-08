import { expect, test } from '@playwright/test'

// T70 Verify (manual half): swipe works; metrics show pass/fail against POC
// targets; OOD banner shows for a run with ood_flag: true. Assumes
// `make dashboard` is running on fixtures with both a hydraulic and a
// surrogate run rendered for the fixture scenario.

test('metrics panel shows PASS/FAIL chips for the surrogate run', async ({ page }) => {
  await page.goto('/')
  const metricsHeading = page.getByRole('heading', { name: 'Metrics' })
  await expect(metricsHeading).toBeVisible({ timeout: 10_000 })

  const chips = page.locator('.metrics-list .chip')
  await expect(chips.first()).toBeVisible()
  const count = await chips.count()
  expect(count).toBeGreaterThan(0)

  // every chip is unambiguously PASS or FAIL -- failures are shown, not hidden
  for (let i = 0; i < count; i++) {
    const text = await chips.nth(i).textContent()
    expect(['PASS', 'FAIL']).toContain(text)
  }
})

test('compare-vs-surrogate toggle enables swipe mode with a divider', async ({ page }) => {
  await page.goto('/')
  const compareButton = page.locator('.compare-toggle')
  await expect(compareButton).toBeEnabled({ timeout: 10_000 })

  await expect(page.locator('.swipe-divider')).toHaveCount(0)
  await compareButton.click()
  await expect(page.locator('.swipe-divider')).toBeVisible()
  await expect(compareButton).toHaveClass(/active/)

  // dragging the divider updates its position without erroring
  const divider = page.locator('.swipe-divider input[type="range"]')
  await divider.fill(String(await divider.getAttribute('min')))

  await compareButton.click()
  await expect(page.locator('.swipe-divider')).toHaveCount(0)
})

test('sigma legend option is selectable (surrogate-only overlay)', async ({ page }) => {
  await page.goto('/')
  const sigmaButton = page.locator('.variable-toggle button', { hasText: 'sigma' })
  await expect(sigmaButton).toBeVisible({ timeout: 10_000 })
  await sigmaButton.click()
  await expect(sigmaButton).toHaveClass(/active/)
  await expect(page.locator('.legend-note')).toHaveText('surrogate only')
})
