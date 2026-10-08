// Typed fetch wrappers over the dashboard API (dashboard/api/*, T30/T40/T50/T53/T54/T71).
// Same-origin requests; vite.config.ts proxies /api, /frames, /thumbs to :8000 in dev.

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${path} -> ${res.status}`)
  return (await res.json()) as T
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(`${path} -> ${res.status}: ${JSON.stringify(detail)}`)
  }
  return (await res.json()) as T
}

export interface ThresholdsConfig {
  depth_bins_m: number[]
  cctv_classes: string[]
  wet_threshold_m: number
  [key: string]: unknown
}

export interface DomainProperties {
  crs: string
  res_m: number
  shape: [number, number]
  is_mock: boolean
}

export interface DomainResponse {
  type: 'Feature'
  geometry: GeoJSON.Geometry | null
  properties: DomainProperties
  crs: string
  res_m: number
  shape: [number, number]
}

export interface ScenarioSummary {
  scenario_id: string
  name: string | null
  categories: string[] | null
  split: string | null
  event_group_id: string | null
  confidence: number | null
  data_class_summary: string | null
  is_mock: boolean
}

export interface RunSummary {
  run_id: string
  source: string
  member_id: string | null
  model_version: string | null
  is_mock: boolean
}

export interface RunFramesManifest {
  run_id: string
  source: string
  var: string
  bounds_wgs84: [number, number, number, number]
  crs_native: string
  t0_utc: string
  dt_s: number | null
  n_frames: number
  colormap: string
  thresholds_m: number[]
  data_class: string
  is_mock: boolean
  model_version: string | null
  surrogate_version: string | null
  scenario_id: string | null
  max_defensible_dt_s: number | null
  frame_url_template: string
}

export interface StationProperties {
  station_id: string
  type: 'rain' | 'level'
  name: string
  source: string
  is_mock: boolean
}

export type StationsGeoJSON = GeoJSON.FeatureCollection<GeoJSON.Point, StationProperties>

export interface StationTimeseries {
  ts: string[]
  value: number[]
  unit: string | null
  data_class: string | null
}

export interface CctvProperties {
  cam_id: string
  source: string
  name_th: string | null
  name_en: string | null
  lon: number
  lat: number
  heading_deg: number | null
  road_name: string | null
  priority: number | null
  in_domain: boolean
  status: string
  is_mock: boolean
}

export type CctvGeoJSON = GeoJSON.FeatureCollection<GeoJSON.Point, CctvProperties>

export interface CctvObservation {
  ts_utc: string
  class: string
  class_smoothed: string | null
  probs: Record<string, number>
  quality_flag: string
  thumb_url: string
}

export interface ValidationResponse {
  metrics: Record<string, number | boolean> | null
  targets: unknown
  points: GeoJSON.FeatureCollection
  gap?: string
}

export interface PredictParams {
  base_scenario_id: string
  rain_scale: number
  duration_stretch: number
  canal_stage_anom_m: number
  outfall_stage_offset_m: number
  drain_multiplier: number
}

export interface PredictJob {
  run_id: string
  status: 'RUNNING' | 'PARTIAL' | 'DONE' | 'FAILED'
  manifest_url?: string
  ood_flag?: boolean
  is_mock?: boolean
  elapsed_s?: number
  error?: string
}

export const api = {
  health: () => getJSON<{ status: string; mode: string; versions: Record<string, string | null> }>('/api/health'),
  config: () => getJSON<ThresholdsConfig>('/api/config'),
  domain: () => getJSON<DomainResponse>('/api/domain'),
  scenarios: (includeMock = true) => getJSON<ScenarioSummary[]>(`/api/scenarios?include_mock=${includeMock}`),
  runs: (params: { scenario_id?: string; source?: string } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString()
    return getJSON<RunSummary[]>(`/api/runs${qs ? `?${qs}` : ''}`)
  },
  runFrames: (runId: string, varName = 'depth') =>
    getJSON<RunFramesManifest>(`/api/runs/${encodeURIComponent(runId)}/frames?var=${varName}`),
  stations: (type?: string) => getJSON<StationsGeoJSON>(`/api/stations${type ? `?type=${type}` : ''}`),
  stationTimeseries: (stationId: string) =>
    getJSON<StationTimeseries>(`/api/stations/${encodeURIComponent(stationId)}/timeseries`),
  cctv: () => getJSON<CctvGeoJSON>('/api/cctv'),
  cctvObservations: (camId: string) =>
    getJSON<{ items: CctvObservation[]; gap?: string }>(`/api/cctv/${encodeURIComponent(camId)}/observations`),
  observations: (scenarioId: string) =>
    getJSON<GeoJSON.FeatureCollection>(`/api/observations?scenario_id=${encodeURIComponent(scenarioId)}`),
  validation: (runId: string) => getJSON<ValidationResponse>(`/api/validation/${encodeURIComponent(runId)}`),
  predict: (params: PredictParams) => postJSON<PredictJob>('/api/predict', params),
  predictStatus: (runId: string) => getJSON<PredictJob>(`/api/predict/${encodeURIComponent(runId)}`),
}
