import { useEffect, useMemo, useState } from 'react'
import type { Layer } from '@deck.gl/core'
import './App.css'
import { MapView } from './map/MapView'
import { domainLayer } from './map/layers/domainLayer'
import { frameLayer, swipeFrameLayers } from './map/layers/frameLayer'
import { camerasLayer, stationsLayer, validationPointsLayer } from './map/layers/pointLayers'
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
import { api, type CctvGeoJSON, type DomainResponse, type RunFramesManifest, type StationsGeoJSON } from './api'
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

  const scenarioId = useAppStore((s) => s.scenarioId)
  const runId = useAppStore((s) => s.runId)
  const setRunId = useAppStore((s) => s.setRunId)
  const tIdx = useAppStore((s) => s.tIdx)
  const setTIdx = useAppStore((s) => s.setTIdx)
  const variable = useAppStore((s) => s.variable)
  const manifest = useAppStore((s) => s.manifest)
  const setManifest = useAppStore((s) => s.setManifest)
  const layers = useAppStore((s) => s.layers)
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

  const bounds = boundsFromPolygon(domain?.geometry ?? null)

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
      const l = stationsLayer(stations, {}, setSelectedStation)
      if (l) result.push(l)
    }
    if (layers.cameras) {
      const l = camerasLayer(cameras, {}, setSelectedCamera)
      if (l) result.push(l)
    }
    const validationLayer = validationPointsLayer(validationPoints)
    if (validationLayer) result.push(validationLayer)
    return result
  }, [domain, manifest, surrogateManifest, tIdx, stations, cameras, layers, compareSource, swipeLon, bounds, validationPoints])

  const anyMock = Boolean(domain?.properties.is_mock || manifest?.is_mock)

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
        <TimeSlider />
        <MockWatermark active={anyMock} />
      </div>
      <aside className={`side-panel ${isMobile ? 'bottom-sheet' : ''}`}>
        <ScenarioSelector />
        {selectedStation && <StationChart stationId={selectedStation} onClose={() => setSelectedStation(null)} />}
        {selectedCamera && <CameraPanel camId={selectedCamera} onClose={() => setSelectedCamera(null)} />}
        {surrogateRunId && <MetricsPanel runId={surrogateRunId} />}
        {!isMobile && <WhatIfPanel />}
      </aside>
      <ProvenanceFooter
        dataClass={manifest?.data_class ?? (domain?.properties.is_mock ? 'SYNTHETIC' : null)}
        modelVersion={manifest?.model_version}
        runId={runId}
      />
    </div>
  )
}
