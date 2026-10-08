import { useEffect, useState } from 'react'
import { api, type ValidationResponse } from '../api'

interface MetricTarget {
  key: string
  label: string
  direction: 'lower-better' | 'higher-better'
  target: number
  unit?: string
  /** compare |value| against target, for metrics that can be signed (e.g. a timing error) */
  absolute?: boolean
}

// [ASSUMPTION] POC targets (§21) aren't available in this repo (the parent
// requirements doc is missing) -- these are a reasonable-looking set for a
// flood feasibility POC, not confirmed numbers. Revisit once §21 lands.
const POC_TARGETS: MetricTarget[] = [
  { key: 'wet_rmse_m', label: 'Wet RMSE', direction: 'lower-better', target: 0.15, unit: 'm' },
  { key: 'csi_0.10', label: 'CSI @ 0.10 m', direction: 'higher-better', target: 0.5 },
  {
    key: 'peak_timing_error_min',
    label: 'Peak timing error',
    direction: 'lower-better',
    target: 30,
    unit: 'min',
    absolute: true,
  },
  {
    key: 'volume_error_pct',
    label: 'Volume error',
    direction: 'lower-better',
    target: 20,
    unit: '%',
    absolute: true,
  },
  { key: 'b1_comparison', label: 'B1 comparison', direction: 'higher-better', target: 0.7 },
  { key: 'coverage_95', label: 'Coverage @ 95%', direction: 'higher-better', target: 0.9 },
]

function passesTarget(t: MetricTarget, value: number): boolean {
  const v = t.absolute ? Math.abs(value) : value
  return t.direction === 'lower-better' ? v <= t.target : v >= t.target
}

export function MetricsPanel({ runId }: { runId: string | null }) {
  const [data, setData] = useState<ValidationResponse | null>(null)

  useEffect(() => {
    if (!runId) {
      setData(null)
      return
    }
    api
      .validation(runId)
      .then(setData)
      .catch(() => setData(null))
  }, [runId])

  if (!runId) return null

  const metrics = data?.metrics
  const knownKeys = new Set(POC_TARGETS.map((t) => t.key))
  const extraEntries = metrics ? Object.entries(metrics).filter(([k]) => k !== 'is_mock' && !knownKeys.has(k)) : []

  return (
    <div className="panel">
      <h3>Metrics</h3>
      {metrics ? (
        <>
          <ul className="metrics-list">
            {POC_TARGETS.map((t) => {
              const raw = metrics[t.key]
              if (typeof raw !== 'number') return null
              const pass = passesTarget(t, raw)
              return (
                <li key={t.key}>
                  <span>{t.label}</span>
                  <span className="metric-value">
                    {raw.toFixed(3)}
                    {t.unit ?? ''}
                    <span className={`chip ${pass ? 'chip-pass' : 'chip-fail'}`}>{pass ? 'PASS' : 'FAIL'}</span>
                  </span>
                </li>
              )
            })}
          </ul>
          {extraEntries.length > 0 && (
            <ul className="metrics-list metrics-list-extra">
              {extraEntries.map(([k, v]) => (
                <li key={k}>
                  <span>{k}</span>
                  <span>{typeof v === 'number' ? v.toFixed(3) : String(v)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <p className="muted">{data?.gap ?? 'No metrics for this run.'}</p>
      )}
    </div>
  )
}
