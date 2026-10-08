import { useEffect, useState } from 'react'
import { api, type ThresholdsConfig } from '../api'
import { useAppStore } from '../store'

// Matches dashboard/render/colormaps.py::depth_v1
const COLORS = ['#c6dbef', '#6baed6', '#2171b5', '#08519c', '#08306b']

const VARIABLES = ['depth', 'extent'] as const

export function Legend() {
  const [config, setConfig] = useState<ThresholdsConfig | null>(null)
  const variable = useAppStore((s) => s.variable)
  const setVariable = useAppStore((s) => s.setVariable)

  useEffect(() => {
    api
      .config()
      .then(setConfig)
      .catch(() => setConfig(null))
  }, [])

  return (
    <div className="legend">
      <div className="variable-toggle">
        {VARIABLES.map((v) => (
          <button
            key={v}
            type="button"
            className={v === variable ? 'active' : ''}
            onClick={() => setVariable(v)}
          >
            {v}
          </button>
        ))}
      </div>
      {variable === 'depth' &&
        config?.depth_bins_m?.map((bin, i) => (
          <span key={bin} className="legend-item">
            <span className="legend-swatch" style={{ background: COLORS[i] ?? COLORS[COLORS.length - 1] }} />
            &ge;{bin}m
          </span>
        ))}
      {variable === 'extent' && (
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: '#2b8cbe' }} />
          &ge;{config?.wet_threshold_m ?? 0.1}m (wet)
        </span>
      )}
    </div>
  )
}
