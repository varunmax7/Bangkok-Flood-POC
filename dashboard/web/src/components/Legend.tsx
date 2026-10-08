import { useEffect, useState } from 'react'
import { api, type ThresholdsConfig } from '../api'
import { useAppStore } from '../store'

// Matches dashboard/render/colormaps.py
const DEPTH_COLORS = ['#c6dbef', '#6baed6', '#2171b5', '#08519c', '#08306b']
const SIGMA_COLORS = ['#bcbddc', '#9e9ac8', '#807dba', '#54278f']
const SIGMA_BINS_M = [0.02, 0.05, 0.1, 0.2]

const VARIABLES = ['depth', 'extent', 'sigma'] as const

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
          <button key={v} type="button" className={v === variable ? 'active' : ''} onClick={() => setVariable(v)}>
            {v}
          </button>
        ))}
      </div>
      {variable === 'depth' &&
        config?.depth_bins_m?.map((bin, i) => (
          <span key={bin} className="legend-item">
            <span className="legend-swatch" style={{ background: DEPTH_COLORS[i] ?? DEPTH_COLORS[DEPTH_COLORS.length - 1] }} />
            &ge;{bin}m
          </span>
        ))}
      {variable === 'extent' && (
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: '#2b8cbe' }} />
          &ge;{config?.wet_threshold_m ?? 0.1}m (wet)
        </span>
      )}
      {variable === 'sigma' && (
        <>
          <span className="legend-note">surrogate only</span>
          {SIGMA_BINS_M.map((bin, i) => (
            <span key={bin} className="legend-item">
              <span className="legend-swatch" style={{ background: SIGMA_COLORS[i] }} />
              &ge;{bin}m
            </span>
          ))}
        </>
      )}
    </div>
  )
}
