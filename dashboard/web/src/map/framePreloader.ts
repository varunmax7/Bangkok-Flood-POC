import type { RunFramesManifest } from '../api'

const cache = new Map<string, HTMLImageElement>()

export function frameUrl(manifest: Pick<RunFramesManifest, 'frame_url_template'>, tIdx: number): string {
  const t = String(tIdx).padStart(3, '0')
  return manifest.frame_url_template.replace('{t:03d}', t)
}

/** Loads (or returns the already-cached) image for a frame URL -- used both
 * for preloading upcoming frames and for timing how long a frame takes to
 * become displayable (the dev perf overlay, ?perf=1). */
export function preloadFrame(url: string): Promise<void> {
  const cached = cache.get(url)
  if (cached?.complete) return Promise.resolve()

  return new Promise((resolve, reject) => {
    const img = cached ?? new Image()
    if (!cached) {
      cache.set(url, img)
      img.src = url
    }
    img.addEventListener('load', () => resolve(), { once: true })
    img.addEventListener('error', () => reject(new Error(`failed to load frame: ${url}`)), { once: true })
    if (img.complete) resolve()
  })
}

export function isFrameCached(url: string): boolean {
  return Boolean(cache.get(url)?.complete)
}
