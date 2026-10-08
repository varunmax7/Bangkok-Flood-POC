import { BitmapLayer } from '@deck.gl/layers'
import type { RunFramesManifest } from '../../api'
import { frameUrl } from '../framePreloader'

export interface FrameLayerOptions {
  opacity?: number
}

export function frameLayer(manifest: RunFramesManifest | null, tIdx: number, opts: FrameLayerOptions = {}) {
  if (!manifest) return null
  return new BitmapLayer({
    id: 'frame',
    image: frameUrl(manifest, tIdx),
    bounds: manifest.bounds_wgs84,
    opacity: opts.opacity ?? 0.85,
  })
}
