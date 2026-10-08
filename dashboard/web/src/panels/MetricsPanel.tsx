import { useEffect, useState } from 'react'
import { api, type ValidationResponse } from '../api'

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

  return (
    <div className="panel">
      <h3>Metrics</h3>
      {data?.metrics ? (
        <ul className="metrics-list">
          {Object.entries(data.metrics)
            .filter(([k]) => k !== 'is_mock')
            .map(([k, v]) => (
              <li key={k}>
                <span>{k}</span>
                <span>{typeof v === 'number' ? v.toFixed(3) : String(v)}</span>
              </li>
            ))}
        </ul>
      ) : (
        <p className="muted">{data?.gap ?? 'No metrics for this run.'}</p>
      )}
    </div>
  )
}
