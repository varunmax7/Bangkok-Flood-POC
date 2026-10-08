import { useEffect, useState } from 'react'
import { api, type ThresholdsConfig } from '../api'

// Matches dashboard/render/colormaps.py::depth_v1
const COLORS = ['#c6dbef', '#6baed6', '#2171b5', '#08519c', '#08306b']

export function Legend() {
  const [config, setConfig] = useState<ThresholdsConfig | null>(null)

  useEffect(() => {
    api
      .config()
      .then(setConfig)
      .catch(() => setConfig(null))
  }, [])

  if (!config?.depth_bins_m) return null

  return (
    <div className="legend">
      {config.depth_bins_m.map((bin, i) => (
        <span key={bin} className="legend-item">
          <span className="legend-swatch" style={{ background: COLORS[i] ?? COLORS[COLORS.length - 1] }} />
          &ge;{bin}m
        </span>
      ))}
    </div>
  )
}
