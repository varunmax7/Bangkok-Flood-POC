import { BitmapLayer } from '@deck.gl/layers'
import { ClipExtension } from '@deck.gl/extensions'
import type { RunFramesManifest } from '../../api'
import { frameUrl } from '../framePreloader'

export interface FrameLayerOptions {
  id?: string
  opacity?: number
  /** [minX, minY, maxX, maxY] in lng/lat -- clips this layer to one side of
   * the swipe divider via deck.gl's ClipExtension. */
  clipBounds?: [number, number, number, number]
}

export function frameLayer(manifest: RunFramesManifest | null, tIdx: number, opts: FrameLayerOptions = {}) {
  if (!manifest) return null
  const props: ConstructorParameters<typeof BitmapLayer>[0] = {
    id: opts.id ?? 'frame',
    image: frameUrl(manifest, tIdx),
    bounds: manifest.bounds_wgs84,
    opacity: opts.opacity ?? 0.85,
  }
  if (opts.clipBounds) {
    props.extensions = [new ClipExtension()]
    // @ts-expect-error -- clipBounds is a ClipExtension prop, not a base BitmapLayer prop
    props.clipBounds = opts.clipBounds
  }
  return new BitmapLayer(props)
}

/** Two BitmapLayers (hydraulic left, surrogate right of swipeLon), each
 * clipped to its half of the domain. */
export function swipeFrameLayers(
  hydraulicManifest: RunFramesManifest | null,
  surrogateManifest: RunFramesManifest | null,
  tIdx: number,
  swipeLon: number,
  domainBounds: [number, number, number, number],
) {
  if (!hydraulicManifest || !surrogateManifest) return []
  const [w, s, e, n] = domainBounds
  const left = frameLayer(hydraulicManifest, tIdx, {
    id: 'swipe-hydraulic',
    clipBounds: [w, s, swipeLon, n],
  })
  const right = frameLayer(surrogateManifest, tIdx, {
    id: 'swipe-surrogate',
    clipBounds: [swipeLon, s, e, n],
  })
  return [left, right].filter((l): l is NonNullable<typeof l> => l !== null)
}
