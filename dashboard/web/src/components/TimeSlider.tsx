import { useEffect, useMemo, useRef, useState } from 'react'
import { useAppStore } from '../store'
import { fmtICT } from '../time'
import { frameUrl, preloadFrame } from '../map/framePreloader'

const FPS_OPTIONS = [2, 3, 4] as const
const PRELOAD_COUNT = 4
const PERF_ROLLING_WINDOW = 10

function usePerfEnabled(): boolean {
  return useMemo(() => new URLSearchParams(window.location.search).get('perf') === '1', [])
}

/** Dev overlay (?perf=1): ms from tIdx change to the frame image finishing
 * load, as a rolling mean over the last PERF_ROLLING_WINDOW switches. */
function usePerfOverlay(enabled: boolean, url: string | null) {
  const [meanMs, setMeanMs] = useState<number | null>(null)
  const samplesRef = useRef<number[]>([])

  useEffect(() => {
    if (!enabled || !url) return
    const t0 = performance.now()
    let cancelled = false
    preloadFrame(url).then(() => {
      if (cancelled) return
      const ms = performance.now() - t0
      const samples = [...samplesRef.current, ms].slice(-PERF_ROLLING_WINDOW)
      samplesRef.current = samples
      const mean = samples.reduce((a, b) => a + b, 0) / samples.length
      setMeanMs(mean)
      // eslint-disable-next-line no-console
      console.log(`[perf] frame switch: ${ms.toFixed(1)}ms (rolling mean: ${mean.toFixed(1)}ms, n=${samples.length})`)
    })
    return () => {
      cancelled = true
    }
  }, [enabled, url])

  return meanMs
}

export function TimeSlider() {
  const manifest = useAppStore((s) => s.manifest)
  const tIdx = useAppStore((s) => s.tIdx)
  const setTIdx = useAppStore((s) => s.setTIdx)
  const playing = useAppStore((s) => s.playing)
  const setPlaying = useAppStore((s) => s.setPlaying)
  const fps = useAppStore((s) => s.fps)
  const setFps = useAppStore((s) => s.setFps)

  const perfEnabled = usePerfEnabled()
  const currentUrl = manifest ? frameUrl(manifest, tIdx) : null
  const perfMeanMs = usePerfOverlay(perfEnabled, currentUrl)

  // Animation loop.
  useEffect(() => {
    if (!playing || !manifest || manifest.n_frames <= 1) return
    const id = window.setInterval(() => {
      useAppStore.setState((s) => ({ tIdx: (s.tIdx + 1) % manifest.n_frames }))
    }, 1000 / fps)
    return () => window.clearInterval(id)
  }, [playing, fps, manifest])

  // Preload the next few frames so playback doesn't stall on fetch.
  useEffect(() => {
    if (!manifest) return
    for (let i = 1; i <= PRELOAD_COUNT; i++) {
      const next = tIdx + i
      if (next >= manifest.n_frames) break
      preloadFrame(frameUrl(manifest, next)).catch(() => {
        /* a missed preload just means that frame loads on demand instead */
      })
    }
  }, [manifest, tIdx])

  if (!manifest) return null

  const t0 = new Date(manifest.t0_utc).getTime()
  const dtMs = (manifest.dt_s ?? 900) * 1000
  const currentIso = new Date(t0 + tIdx * dtMs).toISOString()

  // [ASSUMPTION] manifest.dt_s is a single value for the whole run (no
  // per-frame interval in this schema), so "frames with dt_s <
  // max_defensible_dt_s" is evaluated once for the run and applied to every
  // frame, rather than varying frame-by-frame.
  const isInterpolated =
    manifest.dt_s != null && manifest.max_defensible_dt_s != null && manifest.dt_s < manifest.max_defensible_dt_s

  function handlePlayPause() {
    setPlaying(!playing)
  }

  function handleDragStart() {
    setPlaying(false)
  }

  return (
    <div className="time-slider">
      <button type="button" onClick={handlePlayPause} aria-label={playing ? 'pause' : 'play'} className="play-button">
        {playing ? '❚❚' : '▶'}
      </button>
      <input
        type="range"
        min={0}
        max={Math.max(manifest.n_frames - 1, 0)}
        value={tIdx}
        onMouseDown={handleDragStart}
        onTouchStart={handleDragStart}
        onChange={(e) => setTIdx(Number(e.target.value))}
      />
      <span className={isInterpolated ? 'interpolated' : ''}>
        {fmtICT(currentIso)}
        {isInterpolated && ' (interpolated)'}
      </span>
      <select
        value={fps}
        onChange={(e) => setFps(Number(e.target.value) as 2 | 3 | 4)}
        aria-label="playback speed"
        className="fps-select"
      >
        {FPS_OPTIONS.map((f) => (
          <option key={f} value={f}>
            {f} fps
          </option>
        ))}
      </select>
      {perfEnabled && (
        <span className="perf-overlay" data-testid="perf-overlay">
          {perfMeanMs != null ? `${perfMeanMs.toFixed(0)}ms avg` : 'measuring…'}
        </span>
      )}
    </div>
  )
}
