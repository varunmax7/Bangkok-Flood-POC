import { useEffect, useRef, useState } from 'react'
import { api, type PredictJob, type PredictParams } from '../api'
import { useAppStore } from '../store'

type Params = Omit<PredictParams, 'base_scenario_id'>

const DEFAULTS: Params = {
  rain_scale: 1.0,
  duration_stretch: 1.0,
  canal_stage_anom_m: 0.0,
  outfall_stage_offset_m: 0.0,
  drain_multiplier: 1.0,
}

// §17.5 sampler ranges -- same bounds the backend validates against.
const RANGES: Record<keyof Params, [number, number, number]> = {
  rain_scale: [0.5, 1.8, 0.05],
  duration_stretch: [0.5, 2.0, 0.05],
  canal_stage_anom_m: [-0.3, 0.8, 0.05],
  outfall_stage_offset_m: [0.0, 0.6, 0.02],
  drain_multiplier: [0.3, 1.2, 0.05],
}

export function WhatIfPanel() {
  const scenarioId = useAppStore((s) => s.scenarioId)
  const setOodFlag = useAppStore((s) => s.setOodFlag)
  const [params, setParams] = useState<Params>(DEFAULTS)
  const [job, setJob] = useState<PredictJob | null>(null)
  const [running, setRunning] = useState(false)
  const pollRef = useRef<number | null>(null)

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current)
  }, [])

  async function run() {
    if (!scenarioId) return
    setRunning(true)
    try {
      const started = await api.predict({ base_scenario_id: scenarioId, ...params })
      setJob(started)
      setOodFlag(Boolean(started.ood_flag))
      pollUntilDone(started.run_id)
    } catch (err) {
      setJob({ run_id: '', status: 'FAILED', error: String(err) })
    } finally {
      setRunning(false)
    }
  }

  function pollUntilDone(runId: string) {
    if (pollRef.current) window.clearInterval(pollRef.current)
    pollRef.current = window.setInterval(async () => {
      const status = await api.predictStatus(runId)
      setJob(status)
      if (status.status === 'DONE' || status.status === 'FAILED') {
        if (pollRef.current) window.clearInterval(pollRef.current)
      }
    }, 500)
  }

  return (
    <div className="panel whatif-panel">
      <h3>What if…</h3>
      {(Object.keys(DEFAULTS) as (keyof Params)[]).map((key) => {
        const [min, max, step] = RANGES[key]
        return (
          <label key={key} className="slider-row">
            <span>
              {key} ({params[key]})
            </span>
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={params[key]}
              onChange={(e) => setParams((p) => ({ ...p, [key]: Number(e.target.value) }))}
            />
          </label>
        )
      })}
      <button type="button" onClick={run} disabled={running || !scenarioId}>
        {running ? 'Running…' : 'Run what-if'}
      </button>
      {job && (
        <p className="muted">
          {job.run_id || '—'} &mdash; {job.status}
          {job.elapsed_s != null && ` (${job.elapsed_s}s)`}
          {job.error && `: ${job.error}`}
        </p>
      )}
    </div>
  )
}
