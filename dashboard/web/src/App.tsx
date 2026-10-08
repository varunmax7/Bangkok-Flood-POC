import { useEffect, useMemo, useState } from 'react'
import type { Layer } from '@deck.gl/core'
import './App.css'
import { MapView } from './map/MapView'
import { domainLayer } from './map/layers/domainLayer'
import { frameLayer } from './map/layers/frameLayer'
import { camerasLayer, stationsLayer } from './map/layers/pointLayers'
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
import { api, type CctvGeoJSON, type DomainResponse, type StationsGeoJSON } from './api'
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

  const scenarioId = useAppStore((s) => s.scenarioId)
  const runId = useAppStore((s) => s.runId)
  const setRunId = useAppStore((s) => s.setRunId)
  const tIdx = useAppStore((s) => s.tIdx)
  const manifest = useAppStore((s) => s.manifest)
  const setManifest = useAppStore((s) => s.setManifest)
  const layers = useAppStore((s) => s.layers)

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

  // Pick the first available run for the selected scenario (if any).
  useEffect(() => {
    if (!scenarioId) {
      setRunId(null)
      return
    }
    api
      .runs({ scenario_id: scenarioId })
      .then((runs) => setRunId(runs[0]?.run_id ?? null))
      .catch(() => setRunId(null))
  }, [scenarioId, setRunId])

  useEffect(() => {
    if (!runId) {
      setManifest(null)
      return
    }
    api
      .runFrames(runId)
      .then(setManifest)
      .catch(() => setManifest(null))
  }, [runId, setManifest])

  const deckLayers = useMemo(() => {
    const result: Layer[] = []
    if (layers.domain) {
      const l = domainLayer(domain?.geometry ?? null)
      if (l) result.push(l)
    }
    if (layers.frame) {
      const l = frameLayer(manifest, tIdx)
      if (l) result.push(l)
    }
    if (layers.stations) {
      const l = stationsLayer(stations, {}, setSelectedStation)
      if (l) result.push(l)
    }
    if (layers.cameras) {
      const l = camerasLayer(cameras, {}, setSelectedCamera)
      if (l) result.push(l)
    }
    return result
  }, [domain, manifest, tIdx, stations, cameras, layers])

  const bounds = boundsFromPolygon(domain?.geometry ?? null)
  const anyMock = Boolean(domain?.properties.is_mock || manifest?.is_mock)

  return (
    <div className="app-root">
      <div className="map-area">
        <MapView layers={deckLayers} bounds={bounds} />
        <OodBanner />
        <Legend />
        <TimeSlider />
        <MockWatermark active={anyMock} />
      </div>
      <aside className={`side-panel ${isMobile ? 'bottom-sheet' : ''}`}>
        <ScenarioSelector />
        {selectedStation && <StationChart stationId={selectedStation} onClose={() => setSelectedStation(null)} />}
        {selectedCamera && <CameraPanel camId={selectedCamera} onClose={() => setSelectedCamera(null)} />}
        {runId && <MetricsPanel runId={runId} />}
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
