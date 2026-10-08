import { BitmapLayer } from '@deck.gl/layers'
import type { RunFramesManifest } from '../../api'

/** Static single-frame bitmap at tIdx. T41 adds the slider/animation on top of this. */
export function frameLayer(manifest: RunFramesManifest | null, tIdx: number, opacity = 0.85) {
  if (!manifest) return null
  const t = String(tIdx).padStart(3, '0')
  const url = manifest.frame_url_template.replace('{t:03d}', t)
  return new BitmapLayer({
    id: 'frame',
    image: url,
    bounds: manifest.bounds_wgs84,
    opacity,
  })
}
