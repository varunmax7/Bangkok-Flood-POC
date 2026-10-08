import { expect, test } from '@playwright/test'

// T41 Verify: animation plays all fixture frames; perf target (?perf=1 mean
// frame switch <= 200ms) recorded. Assumes `make dashboard` is running on
// fixtures, with both depth and extent rendered for the fixture hydraulic run.

test('time slider animates and stays within range', async ({ page }) => {
  await page.goto('/')
  const slider = page.locator('.time-slider input[type="range"]')
  await expect(slider).toBeVisible({ timeout: 10_000 })

  const max = Number(await slider.getAttribute('max'))
  expect(max).toBeGreaterThan(0)

  await page.locator('.play-button').click()

  // Headless Chromium's software-rendered WebGL map can make the first
  // real frame update janky enough to delay a tick well past its nominal
  // 500ms interval (confirmed by tracing: the timer always catches up and
  // settles into the correct cadence right after) -- poll generously
  // rather than assume a fixed wall-clock number of ticks lands in a
  // short window.
  await expect.poll(async () => Number(await slider.inputValue()), { timeout: 8_000 }).toBeGreaterThan(0)

  const valueAfterPlay = Number(await slider.inputValue())
  expect(valueAfterPlay).toBeLessThanOrEqual(max)

  // Dragging (mousedown) must pause playback.
  const box = await slider.boundingBox()
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    const valueAtDragStart = Number(await slider.inputValue())
    await page.waitForTimeout(800)
    const valueAfterWait = Number(await slider.inputValue())
    expect(valueAfterWait).toBe(valueAtDragStart) // didn't keep advancing while held
    await page.mouse.up()
  }
})

test('depth/extent toggle switches the rendered variable', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.variable-toggle button', { hasText: 'depth' })).toHaveClass(/active/)

  await page.locator('.variable-toggle button', { hasText: 'extent' }).click()
  await expect(page.locator('.variable-toggle button', { hasText: 'extent' })).toHaveClass(/active/)

  // Frame switching to the other variable set re-fetches a manifest with a
  // fresh frame_url_template; smoke-check nothing crashed and the slider
  // still reflects a valid frame count for the new variable.
  const slider = page.locator('.time-slider input[type="range"]')
  await expect(slider).toBeVisible()
  const max = Number(await slider.getAttribute('max'))
  expect(max).toBeGreaterThan(0)
})

test('perf overlay (?perf=1) reports mean frame-switch time <= 200ms on fixtures', async ({ page }) => {
  await page.goto('/?perf=1')
  const perfOverlay = page.getByTestId('perf-overlay')
  await expect(perfOverlay).toBeVisible({ timeout: 10_000 })

  const slider = page.locator('.time-slider input[type="range"]')
  await expect(slider).toBeVisible()

  // Scrub through several frames to collect perf samples.
  for (let i = 1; i <= 8; i++) {
    await slider.fill(String(i))
    await page.waitForTimeout(150)
  }

  await expect(perfOverlay).not.toHaveText('measuring…', { timeout: 5_000 })
  const text = await perfOverlay.textContent()
  const meanMs = Number(text?.replace('ms avg', '').trim())
  expect(Number.isFinite(meanMs)).toBe(true)
  console.log(`[T41] measured mean frame-switch time on fixtures: ${meanMs}ms`)
  expect(meanMs).toBeLessThanOrEqual(200)
})
