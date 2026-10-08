import { expect, test } from '@playwright/test'

// T60 Verify (manual half): observations layer shows real points filtered to
// the slider's time; satellite layer shows the rendered acquisition or an
// explicit gap; CameraPanel shows a nearest-to-slider-time thumbnail + class
// timeline. Assumes `make dashboard` is running on fixtures with a rendered
// fixture hydraulic run and satellite acquisition (see docs §6 T60).

test('observations toggle shows the road-flood/citizen layer', async ({ page }) => {
  await page.goto('/')
  const toggle = page.locator('.layer-toggle', { hasText: 'observations' })
  await expect(toggle).toBeVisible({ timeout: 10_000 })
  await expect(toggle).toHaveClass(/active/) // on by default

  await toggle.click()
  await expect(toggle).not.toHaveClass(/active/)
  await toggle.click()
  await expect(toggle).toHaveClass(/active/)
})

test('satellite toggle is enabled once a coincident acquisition exists, and shows it', async ({ page }) => {
  await page.goto('/')
  const toggle = page.locator('.layer-toggle', { hasText: 'satellite' })
  await expect(toggle).toBeVisible({ timeout: 10_000 })
  await expect(toggle).toBeEnabled({ timeout: 10_000 })

  await expect(page.locator('canvas').first()).toBeVisible()
  await toggle.click()
  await expect(toggle).toHaveClass(/active/)
  await expect(page.locator('.gap-note')).toHaveCount(0) // the fixture scenario has a real acquisition
})

test('clicking a camera opens its panel with a class timeline', async ({ page, baseURL }) => {
  await page.goto('/')
  const canvas = page.locator('canvas').first()
  await expect(canvas).toBeVisible({ timeout: 10_000 })
  await page.waitForTimeout(1000) // let the first frame + deck.gl layers finish mounting

  const box = await canvas.boundingBox()
  if (!box) throw new Error('map canvas has no bounding box')

  // deck.gl renders to one canvas with no DOM per-feature, so there's no
  // selector for "a camera marker" -- fetch the real registry and use the
  // map instance MapView exposes for tests (window.__map) to project a
  // known camera's lon/lat to an exact pixel instead of guessing.
  const cctv = await page.evaluate(async (url) => (await fetch(`${url}/api/cctv`)).json(), baseURL ?? '')
  const [lon, lat] = cctv.features[0].geometry.coordinates as [number, number]
  const point = await page.evaluate(
    ([lon, lat]) => (window as unknown as { __map: { project: (c: [number, number]) => { x: number; y: number } } }).__map.project([lon, lat]),
    [lon, lat],
  )

  await page.mouse.click(box.x + point.x, box.y + point.y)

  await expect(page.locator('.camera-thumb')).toBeVisible({ timeout: 5000 })
  await expect(page.getByText('Class timeline (scenario window)')).toBeVisible()
})
