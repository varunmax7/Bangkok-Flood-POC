import { expect, test } from '@playwright/test'

// T31 Verify: page loads, map canvas present, footer text present.
// Assumes `make dashboard` (api :8000 + web :5173) is already running on fixtures.

test('dashboard loads with map, panels, footer, and MOCK watermark', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByText('Feasibility prototype')).toBeVisible()

  const mapContainer = page.getByTestId('map-container')
  await expect(mapContainer).toBeVisible()
  await expect(mapContainer.locator('canvas').first()).toBeVisible({ timeout: 10_000 })

  await expect(page.locator('.side-panel')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Scenario' })).toBeVisible()

  // T01 fixtures are all mock -> the watermark must show.
  await expect(page.locator('.mock-watermark')).toContainText('MOCK')

  // Scenario list populated from /api/scenarios (fixture scenario exists).
  await expect(page.locator('.scenario-item').first()).toBeVisible()
})
