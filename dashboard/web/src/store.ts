import { create } from 'zustand'
import type { RunFramesManifest } from './api'

export interface LayerVisibility {
  domain: boolean
  stations: boolean
  cameras: boolean
  frame: boolean
  observations: boolean
  satellite: boolean
}

interface AppState {
  scenarioId: string | null
  runId: string | null
  source: string | null
  compareSource: string | null
  variable: string
  tIdx: number
  playing: boolean
  fps: 2 | 3 | 4
  swipeLon: number | null
  layers: LayerVisibility
  manifest: RunFramesManifest | null
  oodFlag: boolean

  setScenarioId: (id: string | null) => void
  setRunId: (id: string | null) => void
  setSource: (s: string | null) => void
  setCompareSource: (s: string | null) => void
  setVariable: (v: string) => void
  setTIdx: (i: number) => void
  setPlaying: (p: boolean) => void
  setFps: (f: 2 | 3 | 4) => void
  setSwipeLon: (lon: number | null) => void
  toggleLayer: (key: keyof LayerVisibility) => void
  setManifest: (m: RunFramesManifest | null) => void
  setOodFlag: (v: boolean) => void
}

export const useAppStore = create<AppState>()((set) => ({
  scenarioId: null,
  runId: null,
  source: 'hydraulic',
  compareSource: null,
  variable: 'depth',
  tIdx: 0,
  playing: false,
  fps: 2,
  swipeLon: null,
  layers: { domain: true, stations: false, cameras: true, frame: true, observations: false, satellite: false },
  manifest: null,
  oodFlag: false,

  setScenarioId: (id) => set({ scenarioId: id }),
  setRunId: (id) => set({ runId: id }),
  setSource: (s) => set({ source: s }),
  setCompareSource: (s) => set({ compareSource: s }),
  setVariable: (v) => set({ variable: v }),
  setTIdx: (i) => set({ tIdx: i }),
  setPlaying: (p) => set({ playing: p }),
  setFps: (f) => set({ fps: f }),
  setSwipeLon: (lon) => set({ swipeLon: lon }),
  toggleLayer: (key) => set((state) => ({ layers: { ...state.layers, [key]: !state.layers[key] } })),
  setManifest: (m) => set({ manifest: m }),
  setOodFlag: (v) => set({ oodFlag: v }),
}))
