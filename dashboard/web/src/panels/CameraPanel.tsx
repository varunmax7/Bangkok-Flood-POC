import { useEffect, useMemo, useState, type CSSProperties } from 'react'
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

// Matches pointLayers.ts's CLASS_COLORS (map-marker halo) so the side panel's
// badge and the pin it was clicked from always agree on colour.
const CLASS_HEX: Record<string, string> = {
  NORMAL: '#64c864',
  WATERLOGGING: '#e6c83c',
  FLOODING: '#e67828',
  SEVERE_FLOODING: '#c82828',
  UNUSABLE: '#787878',
}

// (prob column, display label, CLASS_HEX key)
const PROB_LABELS: [string, string, string][] = [
  ['p_normal', 'Normal', 'NORMAL'],
  ['p_waterlogging', 'Waterlogging', 'WATERLOGGING'],
  ['p_flooding', 'Flooding', 'FLOODING'],
  ['p_severe', 'Severe flooding', 'SEVERE_FLOODING'],
  ['p_unusable', 'Unusable', 'UNUSABLE'],
]

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
        <div className="camera-row">
          <img src={current.thumb_url} alt={camId} className="camera-thumb" />
          <div className="camera-prediction">
            <span
              className="badge badge-severity"
              style={{ '--severity-color': CLASS_HEX[current.class_smoothed ?? current.class] } as CSSProperties}
            >
              {current.class_smoothed ?? current.class}
            </span>
            <span className="muted camera-prediction-label">visual flood severity proxy &middot; {fmtICT(current.ts_utc)}</span>

            {/* ── Flood Depth Gauge ── */}
            {current.depth_proxy_bin && (
              <div className="depth-gauge-block">
                <div className="depth-gauge-title">Estimated Flood Depth</div>
                <div className="depth-gauge-row">
                  <div className="depth-gauge-bar-wrap">
                    {/* 5 depth bands: 0–5cm, 5–15cm, 15–30cm, 30–50cm, 50cm+ */}
                    {[
                      { label: '0–5 cm', key: 'NORMAL', color: '#64c864' },
                      { label: '5–15 cm', key: 'WATERLOGGING', color: '#e6c83c' },
                      { label: '15–30 cm', key: 'FLOODING', color: '#e67828' },
                      { label: '30–50 cm', key: 'SEVERE_FLOODING', color: '#c82828' },
                      { label: '50+ cm', key: 'SEVERE_FLOODING_HIGH', color: '#7b0000' },
                    ].map((band, i) => {
                      const cls = current.class_smoothed ?? current.class
                      const active =
                        (i === 0 && cls === 'NORMAL') ||
                        (i === 1 && cls === 'WATERLOGGING') ||
                        (i === 2 && cls === 'FLOODING') ||
                        (i === 3 && cls === 'SEVERE_FLOODING' && (current.depth_proxy_m ?? 0) < 0.50) ||
                        (i === 4 && cls === 'SEVERE_FLOODING' && (current.depth_proxy_m ?? 0) >= 0.50)
                      return (
                        <div
                          key={band.label}
                          title={band.label}
                          style={{
                            flex: 1,
                            height: '22px',
                            background: active ? band.color : '#e0e0e0',
                            borderRadius: i === 0 ? '4px 0 0 4px' : i === 4 ? '0 4px 4px 0' : '0',
                            border: active ? `2px solid ${band.color}` : '2px solid transparent',
                            transition: 'all 0.3s',
                          }}
                        />
                      )
                    })}
                  </div>
                </div>
                <div className="depth-gauge-labels">
                  <span>0</span><span>5cm</span><span>15cm</span><span>30cm</span><span>50cm+</span>
                </div>
                <div className="depth-gauge-reading">
                  <span className="depth-value" style={{ color: CLASS_HEX[current.class_smoothed ?? current.class] }}>
                    {current.depth_proxy_m != null
                      ? `~${(current.depth_proxy_m * 100).toFixed(0)} cm (${(current.depth_proxy_m).toFixed(2)} m)`
                      : '—'}
                  </span>
                  <span className="muted"> estimated midpoint</span>
                  {current.is_submerged && <span className="submerged-flag">⚠ vehicle-submerging depth</span>}
                </div>
                {current.water_pixel_pct != null && (
                  <div className="water-pixel-row">
                    <span className="muted">Water pixels detected: </span>
                    <span className="water-pixel-pct" style={{
                      color: current.water_pixel_pct > 0.3 ? '#c82828' : current.water_pixel_pct > 0.1 ? '#e67828' : '#64c864',
                      fontWeight: 600,
                    }}>
                      {(current.water_pixel_pct * 100).toFixed(1)}%
                    </span>
                    <div className="water-pixel-bar-wrap">
                      <div
                        className="water-pixel-bar-fill"
                        style={{
                          width: `${Math.min(current.water_pixel_pct * 100, 100)}%`,
                          background: current.water_pixel_pct > 0.3 ? '#c82828' : current.water_pixel_pct > 0.1 ? '#e67828' : '#64c864',
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="prob-bars">
              {PROB_LABELS.map(([key, label, classKey]) => (
                <div className="prob-bar-row" key={key}>
                  <span className="prob-bar-label">{label}</span>
                  <div className="prob-bar-track">
                    <div
                      className="prob-bar-fill"
                      style={{ width: `${(current.probs[key] ?? 0) * 100}%`, background: CLASS_HEX[classKey] }}
                    />
                  </div>
                  <span className="prob-bar-pct">{((current.probs[key] ?? 0) * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

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
