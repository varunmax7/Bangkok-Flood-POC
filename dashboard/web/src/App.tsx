import { useEffect, useMemo, useState } from 'react'
import type { Layer } from '@deck.gl/core'
import './App.css'
import { MapView } from './map/MapView'
import { domainLayer } from './map/layers/domainLayer'
import { frameLayer, satelliteLayer, swipeFrameLayers } from './map/layers/frameLayer'
import {
  camerasLayer,
  cameraThumbsLayer,
  citizenReportsLayer,
  roadFloodLabelsLayer,
  roadFloodLayer,
  stationsLayer,
  validationPointsLayer,
} from './map/layers/pointLayers'
import { ScenarioSelector } from './panels/ScenarioSelector'
import { StationChart } from './panels/StationChart'
import { CameraPanel } from './panels/CameraPanel'
import { WhatIfPanel } from './panels/WhatIfPanel'
import { MetricsPanel } from './panels/MetricsPanel'
import { TimeSlider } from './components/TimeSlider'
import { Legend } from './components/Legend'
import { OodBanner } from './components/OodBanner'
import { ProvenanceFooter } from './components/ProvenanceFooter'
import { MockWatermark } from './components/MockWatermark'
import { SwipeDivider } from './components/SwipeDivider'
import {
  api,
  type CctvGeoJSON,
  type CctvObservation,
  type DomainResponse,
  type RunFramesManifest,
  type SatelliteAcquisition,
  type StationTimeseries,
  type StationsGeoJSON,
} from './api'
import { frameTimeUtc, nearestByTime, withinMinutesOf } from './time'
import { useAppStore } from './store'

function useIsMobile(breakpointPx = 768) {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < breakpointPx)
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < breakpointPx)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpointPx])
  return isMobile
}

function boundsFromPolygon(geometry: GeoJSON.Geometry | null): [number, number, number, number] | undefined {
  if (!geometry || geometry.type !== 'Polygon') return undefined
  const ring = geometry.coordinates[0]
  const lons = ring.map((p) => p[0])
  const lats = ring.map((p) => p[1])
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)]
}

export default function App() {
  const isMobile = useIsMobile()
  const [domain, setDomain] = useState<DomainResponse | null>(null)
  const [stations, setStations] = useState<StationsGeoJSON | null>(null)
  const [cameras, setCameras] = useState<CctvGeoJSON | null>(null)
  const [selectedStation, setSelectedStation] = useState<string | null>(null)
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null)
  const [surrogateRunId, setSurrogateRunId] = useState<string | null>(null)
  const [surrogateManifest, setSurrogateManifest] = useState<RunFramesManifest | null>(null)
  const [validationPoints, setValidationPoints] = useState<GeoJSON.FeatureCollection | null>(null)
  const [observations, setObservations] = useState<(GeoJSON.FeatureCollection & { gap?: string }) | null>(null)
  const [cameraObsByCam, setCameraObsByCam] = useState<Record<string, CctvObservation[]>>({})
  const [timeseriesByStation, setTimeseriesByStation] = useState<Record<string, StationTimeseries>>({})
  const [satelliteItems, setSatelliteItems] = useState<SatelliteAcquisition[]>([])
  const [satelliteGap, setSatelliteGap] = useState<string | undefined>()

  const scenarioId = useAppStore((s) => s.scenarioId)
  const runId = useAppStore((s) => s.runId)
  const setRunId = useAppStore((s) => s.setRunId)
  const tIdx = useAppStore((s) => s.tIdx)
  const setTIdx = useAppStore((s) => s.setTIdx)
  const variable = useAppStore((s) => s.variable)
  const manifest = useAppStore((s) => s.manifest)
  const setManifest = useAppStore((s) => s.setManifest)
  const layers = useAppStore((s) => s.layers)
  const toggleLayer = useAppStore((s) => s.toggleLayer)
  const compareSource = useAppStore((s) => s.compareSource)
  const setCompareSource = useAppStore((s) => s.setCompareSource)
  const swipeLon = useAppStore((s) => s.swipeLon)

  useEffect(() => {
    api
      .domain()
      .then(setDomain)
      .catch(() => setDomain(null))
    api
      .stations()
      .then(setStations)
      .catch(() => setStations(null))
    api
      .cctv()
      .then(setCameras)
      .catch(() => setCameras(null))
  }, [])

  // Pick the hydraulic run as primary, and track the surrogate run (if any)
  // separately -- swipe/error/metrics all compare the two.
  useEffect(() => {
    if (!scenarioId) {
      setRunId(null)
      setSurrogateRunId(null)
      return
    }
    api
      .runs({ scenario_id: scenarioId })
      .then((runs) => {
        const hydraulic = runs.find((r) => r.source === 'hydraulic')
        const surrogate = runs.find((r) => r.source === 'surrogate')
        setRunId(hydraulic?.run_id ?? runs[0]?.run_id ?? null)
        setSurrogateRunId(surrogate?.run_id ?? null)
      })
      .catch(() => {
        setRunId(null)
        setSurrogateRunId(null)
      })
  }, [scenarioId, setRunId])

  useEffect(() => {
    if (!runId) {
      setManifest(null)
      return
    }
    api
      .runFrames(runId, variable)
      .then((m) => {
        setManifest(m)
        setTIdx(0) // the previous tIdx may be out of range for a different variable's n_frames
      })
      .catch(() => setManifest(null))
  }, [runId, variable, setManifest, setTIdx])

  useEffect(() => {
    if (!surrogateRunId || compareSource !== 'surrogate') {
      setSurrogateManifest(null)
      return
    }
    api
      .runFrames(surrogateRunId, variable)
      .then(setSurrogateManifest)
      .catch(() => setSurrogateManifest(null))
  }, [surrogateRunId, compareSource, variable])

  useEffect(() => {
    if (!surrogateRunId) {
      setValidationPoints(null)
      return
    }
    api
      .validation(surrogateRunId)
      .then((v) => setValidationPoints(v.points ?? null))
      .catch(() => setValidationPoints(null))
  }, [surrogateRunId])

  // T60 observations: DDS road-flood points + Traffy citizen reports for the
  // current scenario, filtered to the slider's time in deckLayers below.
  useEffect(() => {
    if (!scenarioId) {
      setObservations(null)
      return
    }
    api
      .observations(scenarioId)
      .then(setObservations)
      .catch(() => setObservations({ type: 'FeatureCollection', features: [], gap: 'Failed to load observations.' }))
  }, [scenarioId])

  // T60 CameraPanel/camerasLayer: every camera's observation history, fetched
  // once per registry load so both the map (nearest-to-slider-time class)
  // and the panel (full timeline) can read from the same cache.
  useEffect(() => {
    if (!cameras || cameras.features.length === 0) {
      setCameraObsByCam({})
      return
    }
    let cancelled = false
    Promise.all(
      cameras.features.map((f) =>
        api
          .cctvObservations(f.properties.cam_id)
          .then((r) => [f.properties.cam_id, r.items] as const)
          .catch(() => [f.properties.cam_id, []] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setCameraObsByCam(Object.fromEntries(entries))
    })
    return () => {
      cancelled = true
    }
  }, [cameras])

  // T60 stationsLayer: every rain/level gauge's timeseries, fetched once so
  // the rain-gauge radius can be recomputed locally as the slider moves
  // instead of refetching per frame.
  useEffect(() => {
    if (!stations || stations.features.length === 0) {
      setTimeseriesByStation({})
      return
    }
    let cancelled = false
    Promise.all(
      stations.features.map((f) =>
        api
          .stationTimeseries(f.properties.station_id)
          .then((ts) => [f.properties.station_id, ts] as const)
          .catch(() => [f.properties.station_id, null] as const),
      ),
    ).then((entries) => {
      if (!cancelled) {
        const found = entries.filter((e): e is [string, StationTimeseries] => e[1] !== null)
        setTimeseriesByStation(Object.fromEntries(found))
      }
    })
    return () => {
      cancelled = true
    }
  }, [stations])

  // T60 satellite: acquisitions for the primary (hydraulic) run's scenario.
  useEffect(() => {
    if (!runId) {
      setSatelliteItems([])
      setSatelliteGap(undefined)
      return
    }
    api
      .runSatellite(runId)
      .then((r) => {
        setSatelliteItems(r.items)
        setSatelliteGap(r.gap)
      })
      .catch(() => {
        setSatelliteItems([])
        setSatelliteGap('Failed to load satellite data.')
      })
  }, [runId])

  const bounds = boundsFromPolygon(domain?.geometry ?? null)
  const sliderTimeUtc = manifest ? frameTimeUtc(manifest.t0_utc, manifest.dt_s, tIdx) : null

  // Observations near the slider's time (±30 min) -- road-flood/citizen
  // reports are snapshots, not a continuous field, so showing the whole
  // scenario's worth at once would be misleading about "now".
  const filteredObservations = useMemo(() => {
    if (!observations || !sliderTimeUtc) return null
    const features = observations.features.filter(
      (f) => typeof f.properties?.ts_utc === 'string' && withinMinutesOf(f.properties.ts_utc, sliderTimeUtc, 30),
    )
    return { ...observations, features }
  }, [observations, sliderTimeUtc])

  // Nearest-to-slider-time observation per camera -- falls back to the
  // latest-known one when no scenario/run is loaded yet (sliderTimeUtc is
  // null), same convention CameraPanel itself uses, so a camera's dot/photo
  // shows up on the map as soon as its registry+observations load rather
  // than only after the user picks a scenario.
  const latestObsByCam = useMemo(() => {
    const out: Record<string, CctvObservation> = {}
    for (const [camId, items] of Object.entries(cameraObsByCam)) {
      if (items.length === 0) continue
      const obs = sliderTimeUtc ? (nearestByTime(items, sliderTimeUtc, (i) => i.ts_utc) ?? items[items.length - 1]) : items[items.length - 1]
      out[camId] = obs
    }
    return out
  }, [cameraObsByCam, sliderTimeUtc])

  // Map shows only the manually-captured cameras (MANUAL-000N) -- the mock
  // BMAT/ITIC/LNGD fixture cameras stay in the registry/API (other panels
  // and tests rely on the full set) but are noisy on the map itself: 10 of
  // them plus 5 manual spots at this domain's zoom level overlapped into an
  // unreadable cluster, which is what prompted filtering down to just the
  // 5 real photo spots the user actually wants to see.
  const manualCameras = useMemo((): CctvGeoJSON | null => {
    if (!cameras) return null
    return { ...cameras, features: cameras.features.filter((f) => f.properties.source === 'MANUAL') }
  }, [cameras])

  // camerasLayer's colouring.
  const classByCam = useMemo(() => {
    const out: Record<string, string> = {}
    for (const [camId, obs] of Object.entries(latestObsByCam)) {
      out[camId] = obs.class_smoothed ?? obs.class
    }
    return out
  }, [latestObsByCam])

  // cameraThumbsLayer's photo per camera -- agrees with classByCam above on
  // which observation each camera shows, since both derive from latestObsByCam.
  const thumbByCam = useMemo(() => {
    const out: Record<string, string> = {}
    for (const [camId, obs] of Object.entries(latestObsByCam)) {
      out[camId] = obs.thumb_url
    }
    return out
  }, [latestObsByCam])

  // Rain-gauge radius = rain in the hour ending at the slider's time
  // (stations.timeseries is per-15-min totals -- see docs/assumptions.md).
  const rainByStation = useMemo(() => {
    if (!sliderTimeUtc || !stations) return {}
    const targetMs = new Date(sliderTimeUtc).getTime()
    const windowMs = 60 * 60_000
    const out: Record<string, number> = {}
    for (const f of stations.features) {
      if (f.properties.type !== 'rain') continue
      const ts = timeseriesByStation[f.properties.station_id]
      if (!ts) continue
      let sum = 0
      for (let i = 0; i < ts.ts.length; i++) {
        const t = new Date(ts.ts[i]).getTime()
        if (t <= targetMs && t > targetMs - windowMs) sum += ts.value[i] ?? 0
      }
      out[f.properties.station_id] = sum
    }
    return out
  }, [stations, timeseriesByStation, sliderTimeUtc])

  const selectedSatelliteAcquisition = useMemo(() => {
    if (satelliteItems.length === 0 || !sliderTimeUtc) return null
    return nearestByTime(satelliteItems, sliderTimeUtc, (a) => a.ts_utc)
  }, [satelliteItems, sliderTimeUtc])

  const deckLayers = useMemo(() => {
    const result: Layer[] = []
    if (layers.domain) {
      const l = domainLayer(domain?.geometry ?? null)
      if (l) result.push(l)
    }
    if (layers.frame) {
      if (compareSource === 'surrogate' && bounds) {
        const lon = swipeLon ?? (bounds[0] + bounds[2]) / 2
        result.push(...swipeFrameLayers(manifest, surrogateManifest, tIdx, lon, bounds))
      } else {
        const l = frameLayer(manifest, tIdx)
        if (l) result.push(l)
      }
    }
    if (layers.stations) {
      const l = stationsLayer(stations, rainByStation, setSelectedStation)
      if (l) result.push(l)
    }
    if (layers.cameras) {
      const l = camerasLayer(manualCameras, classByCam, setSelectedCamera)
      if (l) result.push(l)
      const thumbs = cameraThumbsLayer(manualCameras, thumbByCam, setSelectedCamera)
      if (thumbs) result.push(thumbs)
    }
    if (layers.observations) {
      const road = roadFloodLayer(filteredObservations)
      if (road) result.push(road)
      const roadLabels = roadFloodLabelsLayer(filteredObservations)
      if (roadLabels) result.push(roadLabels)
      const citizen = citizenReportsLayer(filteredObservations)
      if (citizen) result.push(citizen)
    }
    if (layers.satellite) {
      const sat = satelliteLayer(selectedSatelliteAcquisition)
      if (sat) result.push(sat)
    }
    const validationLayer = validationPointsLayer(validationPoints)
    if (validationLayer) result.push(validationLayer)
    return result
  }, [
    domain,
    manifest,
    surrogateManifest,
    tIdx,
    stations,
    manualCameras,
    layers,
    compareSource,
    swipeLon,
    bounds,
    validationPoints,
    rainByStation,
    classByCam,
    thumbByCam,
    filteredObservations,
    selectedSatelliteAcquisition,
  ])

  // "whenever any rendered item has is_mock" -- check every visible layer's
  // data, not just the current frame, so swiping to a mock surrogate run or
  // loading a mock-only camera/station registry still shows the watermark.
  const anyMock = Boolean(
    domain?.properties.is_mock ||
      manifest?.is_mock ||
      surrogateManifest?.is_mock ||
      stations?.features.some((f) => f.properties.is_mock) ||
      cameras?.features.some((f) => f.properties.is_mock),
  )

  return (
    <div className="app-root">
      <div className="map-area">
        <MapView layers={deckLayers} bounds={bounds} />
        <OodBanner />
        <Legend />
        <button
          type="button"
          className={`compare-toggle ${compareSource === 'surrogate' ? 'active' : ''}`}
          disabled={!surrogateRunId}
          onClick={() => setCompareSource(compareSource === 'surrogate' ? null : 'surrogate')}
        >
          {compareSource === 'surrogate' ? '✕ exit compare' : '⇄ compare vs surrogate'}
        </button>
        {compareSource === 'surrogate' && bounds && <SwipeDivider domainBounds={bounds} />}
        <div className="layer-toggle-row">
          <button
            type="button"
            className={`layer-toggle ${layers.observations ? 'active' : ''}`}
            onClick={() => toggleLayer('observations')}
          >
            {layers.observations ? '✕ hide observations' : '📍 show observations'}
          </button>
          <button
            type="button"
            className={`layer-toggle ${layers.satellite ? 'active' : ''}`}
            disabled={satelliteItems.length === 0}
            onClick={() => toggleLayer('satellite')}
          >
            {layers.satellite ? '✕ hide satellite' : '🛰️ show satellite'}
          </button>
          {layers.satellite && satelliteGap && <p className="muted gap-note">{satelliteGap}</p>}
        </div>
        <TimeSlider />
        <MockWatermark active={anyMock} />
      </div>
      <aside className={`side-panel ${isMobile ? 'bottom-sheet' : ''}`}>
        <ScenarioSelector />
        {selectedStation && <StationChart stationId={selectedStation} onClose={() => setSelectedStation(null)} />}
        {selectedCamera && (
          <CameraPanel camId={selectedCamera} sliderTimeUtc={sliderTimeUtc} onClose={() => setSelectedCamera(null)} />
        )}
        {surrogateRunId && <MetricsPanel runId={surrogateRunId} />}
        {!isMobile && <WhatIfPanel />}
      </aside>
      <ProvenanceFooter
        dataClass={manifest?.data_class ?? (domain?.properties.is_mock ? 'SYNTHETIC' : null)}
        modelVersion={manifest?.model_version}
        surrogateVersion={manifest?.surrogate_version}
        runId={runId}
      />
    </div>
  )
}
