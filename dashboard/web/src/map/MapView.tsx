import { useEffect, useRef } from 'react'
import { Map as MapLibreMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapboxOverlay } from '@deck.gl/mapbox'
import type { Layer } from '@deck.gl/core'

// Carto Positron, no API key needed. [ASSUMPTION] the card says "raster ...
// no key", but CARTO's classic anonymous raster XYZ endpoint
// (basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png) now watermarks tiles
// with "API KEY REQUIRED" for keyless requests (a policy change since this
// plan was written -- verified directly, not assumed). Their GL vector
// style at this URL remains genuinely free/keyless and is the officially
// documented way to use Positron with MapLibre today.
const CARTO_POSITRON_STYLE_URL = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

interface MapViewProps {
  layers: Layer[]
  /** [west, south, east, north] -- fit once, on first availability. */
  bounds?: [number, number, number, number]
}

export function MapView({ layers, bounds }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const overlayRef = useRef<MapboxOverlay | null>(null)
  const firstFitRef = useRef(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new MapLibreMap({
      container: containerRef.current,
      style: CARTO_POSITRON_STYLE_URL,
      center: [100.58, 13.84],
      zoom: 11,
    })
    // Non-interleaved: deck.gl draws on its own canvas on top of the map's,
    // instead of sharing maplibre's WebGL context/draw calls. None of our
    // layers (domain outline, points, a flat bitmap) need true 3D
    // interleaving with map geometry, and sharing the context turned out to
    // be fragile -- when deck.gl's interleaved custom-layer render threw
    // ("Cannot read properties of undefined (reading '_nearZ'/'height')"),
    // it sometimes corrupted shared GL state badly enough that maplibre's
    // *own* tile layer stopped (re)painting too, intermittently leaving the
    // whole map blank.
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] })
    // Also wait for 'load': adding the control synchronously, right after
    // map creation, interfered with maplibre's own style pipeline here --
    // only style.json ever got fetched, never the sprite/tiles/fonts it
    // references, leaving the basemap permanently blank.
    map.on('load', () => map.addControl(overlay))
    mapRef.current = map
    overlayRef.current = overlay
    return () => {
      map.remove()
      mapRef.current = null
      overlayRef.current = null
    }
  }, [])

  useEffect(() => {
    overlayRef.current?.setProps({ layers })
  }, [layers])

  useEffect(() => {
    if (!mapRef.current || !bounds || firstFitRef.current) return
    const [w, s, e, n] = bounds
    mapRef.current.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: 40, duration: 0 },
    )
    firstFitRef.current = true
  }, [bounds])

  return (
    // inline position/inset, not just the .map-container class: maplibre-gl.css
    // sets `.maplibregl-map { position: relative }` on this same element (it's
    // the container we handed to `new MapLibreMap(...)`), which has equal CSS
    // specificity to our class and can win the cascade depending on import
    // order, collapsing this to zero height. Inline style always wins.
    <div
      ref={containerRef}
      className="map-container"
      data-testid="map-container"
      style={{ position: 'absolute', inset: 0 }}
    />
  )
}
