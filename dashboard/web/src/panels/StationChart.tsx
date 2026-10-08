import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api, type StationTimeseries } from '../api'
import { fmtICT, fmtTooltip } from '../time'

interface StationChartProps {
  stationId: string
  onClose: () => void
}

export function StationChart({ stationId, onClose }: StationChartProps) {
  const [ts, setTs] = useState<StationTimeseries | null>(null)

  useEffect(() => {
    setTs(null)
    api
      .stationTimeseries(stationId)
      .then(setTs)
      .catch(() => setTs(null))
  }, [stationId])

  const data = ts ? ts.ts.map((t, i) => ({ ts: t, value: ts.value[i] })) : []
  const formatLabel = (value: unknown) => (typeof value === 'string' ? fmtTooltip(value) : String(value ?? ''))

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>{stationId}</h3>
        <button type="button" onClick={onClose} aria-label="close">
          &times;
        </button>
      </div>
      <p className="muted">Rain totals use a 07:00-07:00 ICT daily window.</p>
      {ts ? (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data}>
            <XAxis dataKey="ts" tickFormatter={(value: string) => fmtICT(value)} hide />
            <YAxis unit={ts.unit ?? ''} width={48} />
            <Tooltip labelFormatter={formatLabel} />
            <Line type="monotone" dataKey="value" stroke="#3878dc" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="muted">Loading…</p>
      )}
    </div>
  )
}
