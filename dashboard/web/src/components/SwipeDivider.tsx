import { useAppStore } from '../store'

interface SwipeDividerProps {
  /** [west, south, east, north] -- the swipe divider ranges across the domain's lon span. */
  domainBounds: [number, number, number, number]
}

/** A horizontal 0-100% slider mapped linearly across the domain's longitude
 * span. The domain here is small enough (~0.1 degree) that map-projection
 * distortion across it is negligible, so this avoids needing the MapLibre
 * instance's own screen<->lnglat projection just for a swipe control. */
export function SwipeDivider({ domainBounds }: SwipeDividerProps) {
  const [w, , e] = domainBounds
  const swipeLon = useAppStore((s) => s.swipeLon)
  const setSwipeLon = useAppStore((s) => s.setSwipeLon)

  const lon = swipeLon ?? (w + e) / 2
  const pct = ((lon - w) / (e - w)) * 100

  return (
    <div className="swipe-divider">
      <input
        type="range"
        min={w}
        max={e}
        step={(e - w) / 200}
        value={lon}
        onChange={(ev) => setSwipeLon(Number(ev.target.value))}
        style={{ ['--pct' as string]: `${pct}%` }}
      />
      <span className="swipe-label swipe-label-left">hydraulic</span>
      <span className="swipe-label swipe-label-right">surrogate</span>
    </div>
  )
}
