import { ScatterplotLayer } from '@deck.gl/layers'
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

export function camerasLayer(fc: CctvGeoJSON | null, classByCam: Record<string, string>, onClick: (camId: string) => void) {
  if (!fc) return null
  return new ScatterplotLayer<CctvFeature>({
    id: 'cameras',
    data: fc.features,
    getPosition: (f) => f.geometry.coordinates as [number, number],
    getRadius: 90,
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
