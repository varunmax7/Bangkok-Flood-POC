import { GeoJsonLayer } from '@deck.gl/layers'

export function domainLayer(geometry: GeoJSON.Geometry | null) {
  if (!geometry) return null
  return new GeoJsonLayer({
    id: 'domain',
    data: { type: 'Feature', geometry, properties: {} },
    stroked: true,
    filled: false,
    // Dark, not white: the basemap (Positron) is itself very light, so a
    // white stroke has almost no contrast against it.
    getLineColor: [30, 41, 59, 220],
    lineWidthMinPixels: 3,
  })
}
