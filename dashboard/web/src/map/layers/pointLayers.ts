import { IconLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import type { PickingInfo } from '@deck.gl/core'
import type { CctvGeoJSON, CctvProperties, StationsGeoJSON, StationProperties } from '../../api'

type StationFeature = StationsGeoJSON['features'][number]
type CctvFeature = CctvGeoJSON['features'][number]

const CLASS_COLORS: Record<string, [number, number, number, number]> = {
  NORMAL: [100, 200, 100, 220],
  WATERLOGGING: [230, 200, 60, 220],
  FLOODING: [230, 120, 40, 220],
  SEVERE_FLOODING: [200, 40, 40, 220],
  UNUSABLE: [120, 120, 120, 220],
}
const UNKNOWN_COLOR: [number, number, number, number] = [150, 150, 150, 160]

export function stationsLayer(
  fc: StationsGeoJSON | null,
  rainByStation: Record<string, number>,
  onClick: (stationId: string) => void,
) {
  if (!fc) return null
  return new ScatterplotLayer<StationFeature>({
    id: 'stations',
    data: fc.features,
    getPosition: (f) => f.geometry.coordinates as [number, number],
    getRadius: (f: StationFeature) => 80 + 40 * (rainByStation[f.properties.station_id] ?? 0),
    radiusUnits: 'meters',
    getFillColor: (f: StationFeature) => (f.properties.type === 'rain' ? [50, 120, 220, 210] : [30, 180, 180, 210]),
    stroked: true,
    getLineColor: [20, 20, 20, 200],
    lineWidthMinPixels: 1,
    pickable: true,
    onClick: (info: PickingInfo<StationFeature>) => {
      const props = info.object?.properties as StationProperties | undefined
      if (props) onClick(props.station_id)
    },
  })
}

// [ASSUMPTION] GET /api/validation/{run_id}'s `points` FeatureCollection is
// always empty today (store.py doesn't compute real hit/miss points yet --
// that needs observation<->model joining logic outside T70's file list).
// This renders a `hit: boolean` property convention so the layer is ready
// the moment the backend populates it, without guessing a different schema.
export function validationPointsLayer(fc: GeoJSON.FeatureCollection | null) {
  if (!fc || fc.features.length === 0) return null
  return new ScatterplotLayer({
    id: 'validation-points',
    data: fc.features,
    getPosition: (f: GeoJSON.Feature) => (f.geometry as GeoJSON.Point).coordinates as [number, number],
    getRadius: 60,
    radiusUnits: 'meters',
    getFillColor: (f: GeoJSON.Feature) => (f.properties?.hit ? [80, 200, 100, 220] : [220, 60, 60, 220]),
    stroked: true,
    getLineColor: [20, 20, 20, 200],
    lineWidthMinPixels: 1,
    pickable: true,
  })
}

// ----------------------------------------------------------------- T60 ---
// DDS road-flood points (labelled with depth in cm) + Traffy citizen reports
// (clustered -- grid-binned here rather than pulling in a whole aggregation
// library for one layer), both pre-filtered by the caller to "near the
// slider's time" (see time.ts::withinMinutesOf).

type ObservationFeature = GeoJSON.Feature<GeoJSON.Point, { kind: 'road_flood' | 'citizen'; depth_cm?: number }>

function _roadFloodFeatures(fc: GeoJSON.FeatureCollection | null): ObservationFeature[] {
  return ((fc?.features ?? []) as ObservationFeature[]).filter((f) => f.properties.kind === 'road_flood')
}

function _citizenFeatures(fc: GeoJSON.FeatureCollection | null): ObservationFeature[] {
  return ((fc?.features ?? []) as ObservationFeature[]).filter((f) => f.properties.kind === 'citizen')
}

// Matches configs/thresholds.yaml's cctv_depth_proxy_bins_m (converted m -> cm).
function depthCmColor(depthCm: number | undefined): [number, number, number, number] {
  const cm = depthCm ?? 0
  if (cm < 5) return [100, 200, 100, 220]
  if (cm < 15) return [230, 200, 60, 220]
  if (cm < 30) return [230, 120, 40, 220]
  return [200, 40, 40, 220]
}

export function roadFloodLayer(fc: GeoJSON.FeatureCollection | null) {
  const features = _roadFloodFeatures(fc)
  if (features.length === 0) return null
  return new ScatterplotLayer<ObservationFeature>({
    id: 'road-flood-observations',
    data: features,
    getPosition: (f) => f.geometry.coordinates as [number, number],
    getRadius: 45,
    radiusUnits: 'meters',
    getFillColor: (f) => depthCmColor(f.properties.depth_cm),
    stroked: true,
    getLineColor: [20, 20, 20, 200],
    lineWidthMinPixels: 1,
    pickable: true,
  })
}

export function roadFloodLabelsLayer(fc: GeoJSON.FeatureCollection | null) {
  const features = _roadFloodFeatures(fc)
  if (features.length === 0) return null
  return new TextLayer<ObservationFeature>({
    id: 'road-flood-depth-labels',
    data: features,
    getPosition: (f) => f.geometry.coordinates as [number, number],
    getText: (f) => (f.properties.depth_cm != null ? `${Math.round(f.properties.depth_cm)}cm` : '?'),
    getSize: 11,
    getColor: [30, 30, 30, 255],
    getPixelOffset: [0, -16],
    background: true,
    getBackgroundColor: [255, 255, 255, 190],
    backgroundPadding: [3, 1],
  })
}

// Grid-binned cluster centers (not a real clustering algorithm -- fine at
// this POC's point density); radius grows with sqrt(count) so area, not
// radius, scales linearly with report count.
function clusterByGridCell(features: ObservationFeature[], cellSizeDeg: number): { position: [number, number]; count: number }[] {
  const cells = new Map<string, { sumLon: number; sumLat: number; count: number }>()
  for (const f of features) {
    const [lon, lat] = f.geometry.coordinates as [number, number]
    const key = `${Math.floor(lon / cellSizeDeg)}:${Math.floor(lat / cellSizeDeg)}`
    const cell = cells.get(key) ?? { sumLon: 0, sumLat: 0, count: 0 }
    cell.sumLon += lon
    cell.sumLat += lat
    cell.count += 1
    cells.set(key, cell)
  }
  return [...cells.values()].map((c) => ({ position: [c.sumLon / c.count, c.sumLat / c.count], count: c.count }))
}

export function citizenReportsLayer(fc: GeoJSON.FeatureCollection | null, cellSizeDeg = 0.003) {
  const features = _citizenFeatures(fc)
  if (features.length === 0) return null
  const clusters = clusterByGridCell(features, cellSizeDeg)
  return new ScatterplotLayer<{ position: [number, number]; count: number }>({
    id: 'citizen-reports-clustered',
    data: clusters,
    getPosition: (c) => c.position,
    getRadius: (c) => 55 + 35 * Math.sqrt(c.count),
    radiusUnits: 'meters',
    getFillColor: [180, 100, 220, 170],
    stroked: true,
    getLineColor: [80, 30, 120, 200],
    lineWidthMinPixels: 1,
    pickable: true,
  })
}

export function camerasLayer(fc: CctvGeoJSON | null, classByCam: Record<string, string>, onClick: (camId: string) => void) {
  if (!fc) return null
  return new ScatterplotLayer<CctvFeature>({
    id: 'cameras',
    data: fc.features,
    getPosition: (f) => f.geometry.coordinates as [number, number],
    // Slightly larger than the thumbnail icon on top of it, so it reads as a
    // severity-coloured halo around the photo rather than competing with it.
    getRadius: 110,
    radiusUnits: 'meters',
    getFillColor: (f: CctvFeature) => CLASS_COLORS[classByCam[f.properties.cam_id] ?? ''] ?? UNKNOWN_COLOR,
    stroked: true,
    getLineColor: [20, 20, 20, 200],
    lineWidthMinPixels: 1,
    pickable: true,
    onClick: (info: PickingInfo<CctvFeature>) => {
      const props = info.object?.properties as CctvProperties | undefined
      if (props) onClick(props.cam_id)
    },
  })
}

// Renders the actual (blurred) CCTV thumbnail at each camera's map position,
// layered on top of `camerasLayer`'s severity-coloured dot so the colour
// still reads as a halo behind the photo. Only drawn for cameras that have a
// thumbnail at/near the slider's time (see App.tsx's `thumbByCam`); cameras
// without one yet keep showing just the plain coloured dot underneath.
export function cameraThumbsLayer(
  fc: CctvGeoJSON | null,
  thumbByCam: Record<string, string>,
  onClick: (camId: string) => void,
) {
  if (!fc) return null
  const features = fc.features.filter((f) => thumbByCam[f.properties.cam_id])
  if (features.length === 0) return null
  return new IconLayer<CctvFeature>({
    id: 'camera-thumbs',
    data: features,
    getPosition: (f) => f.geometry.coordinates as [number, number],
    getIcon: (f: CctvFeature) => ({
      url: thumbByCam[f.properties.cam_id],
      width: 64,
      height: 48,
      anchorX: 32,
      anchorY: 24,
    }),
    sizeUnits: 'pixels',
    getSize: 48,
    pickable: true,
    onClick: (info: PickingInfo<CctvFeature>) => {
      const props = info.object?.properties as CctvProperties | undefined
      if (props) onClick(props.cam_id)
    },
  })
}
