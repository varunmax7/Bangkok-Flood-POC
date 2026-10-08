import { useEffect, useMemo, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type CctvObservation } from '../api'
import { fmtICT, fmtTooltip, nearestByTime } from '../time'

interface CameraPanelProps {
  camId: string
  /** Current slider instant (manifest t0 + tIdx*dt), if a run is loaded --
   * picks the observation nearest this time, not just the newest overall. */
  sliderTimeUtc: string | null
  onClose: () => void
}

// NORMAL < WATERLOGGING < FLOODING < SEVERE_FLOODING as a step chart;
// UNUSABLE sits below NORMAL (quality_flag-gated, not a severity reading).
const CLASS_SEVERITY: Record<string, number> = {
  UNUSABLE: -1,
  NORMAL: 0,
  WATERLOGGING: 1,
  FLOODING: 2,
  SEVERE_FLOODING: 3,
}
const SEVERITY_LABEL = Object.fromEntries(Object.entries(CLASS_SEVERITY).map(([k, v]) => [v, k]))

export function CameraPanel({ camId, sliderTimeUtc, onClose }: CameraPanelProps) {
  const [items, setItems] = useState<CctvObservation[]>([])
  const [gap, setGap] = useState<string | undefined>()

  useEffect(() => {
    setItems([])
    setGap(undefined)
    api
      .cctvObservations(camId)
      .then((r) => {
        setItems(r.items)
        setGap(r.gap)
      })
      .catch(() => setGap('Failed to load observations.'))
  }, [camId])

  const current = useMemo(() => {
    if (items.length === 0) return undefined
    if (!sliderTimeUtc) return items[items.length - 1]
    return nearestByTime(items, sliderTimeUtc, (i) => i.ts_utc) ?? items[items.length - 1]
  }, [items, sliderTimeUtc])

  const timelineData = useMemo(
    () =>
      items.map((i) => {
        const cls = i.class_smoothed ?? i.class
        return { ts: i.ts_utc, severity: CLASS_SEVERITY[cls] ?? -1, label: cls }
      }),
    [items],
  )

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>{camId}</h3>
        <button type="button" onClick={onClose} aria-label="close">
          &times;
        </button>
      </div>
      {current ? (
        <>
          <img src={current.thumb_url} alt={camId} className="camera-thumb" />
          <p>
            <span className="badge">{current.class_smoothed ?? current.class}</span>
            <span className="muted"> visual flood severity proxy &middot; {fmtICT(current.ts_utc)}</span>
          </p>
        </>
      ) : (
        <p className="muted">{gap ?? 'Loading…'}</p>
      )}
      {timelineData.length > 1 && (
        <>
          <p className="muted">Class timeline (scenario window)</p>
          <ResponsiveContainer width="100%" height={110}>
            <LineChart data={timelineData}>
              <XAxis dataKey="ts" tickFormatter={(value: string) => fmtICT(value)} hide />
              <YAxis
                domain={[-1, 3]}
                ticks={[-1, 0, 1, 2, 3]}
                width={96}
                tickFormatter={(value: number) => SEVERITY_LABEL[value] ?? ''}
              />
              <Tooltip
                labelFormatter={(value: unknown) => (typeof value === 'string' ? fmtTooltip(value) : String(value ?? ''))}
                formatter={(value, _name, item) => {
                  const payload = (item as { payload?: { label?: string } }).payload
                  return [payload?.label ?? String(value ?? ''), 'class']
                }}
              />
              <Line type="stepAfter" dataKey="severity" stroke="#cc6622" dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
