import { useAppStore } from '../store'
import { fmtICT } from '../time'

/** Static scrub slider for T31; T41 adds play/pause + preloading on top. */
export function TimeSlider() {
  const manifest = useAppStore((s) => s.manifest)
  const tIdx = useAppStore((s) => s.tIdx)
  const setTIdx = useAppStore((s) => s.setTIdx)

  if (!manifest) return null

  const t0 = new Date(manifest.t0_utc).getTime()
  const dtMs = (manifest.dt_s ?? 900) * 1000
  const currentIso = new Date(t0 + tIdx * dtMs).toISOString()

  return (
    <div className="time-slider">
      <input
        type="range"
        min={0}
        max={Math.max(manifest.n_frames - 1, 0)}
        value={tIdx}
        onChange={(e) => setTIdx(Number(e.target.value))}
      />
      <span>{fmtICT(currentIso)}</span>
    </div>
  )
}
