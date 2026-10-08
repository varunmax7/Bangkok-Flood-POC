const ICT_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Bangkok',
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** ICT wall-clock time for an ISO-8601 UTC timestamp. */
export function fmtICT(isoUtc: string): string {
  return `${ICT_FORMATTER.format(new Date(isoUtc))} ICT`
}

export function fmtUTC(isoUtc: string): string {
  return `${isoUtc} UTC`
}

/** For tooltips: ICT first (what people read), UTC alongside (what's stored). */
export function fmtTooltip(isoUtc: string): string {
  return `${fmtICT(isoUtc)} (${fmtUTC(isoUtc)})`
}

/** The UTC instant a manifest's frame index corresponds to (T60: used to
 * filter observations/rain-gauge radius to "near the slider's time"). */
export function frameTimeUtc(t0Utc: string, dtS: number | null, tIdx: number): string {
  const stepMs = (dtS ?? 0) * 1000
  return new Date(new Date(t0Utc).getTime() + tIdx * stepMs).toISOString().replace(/\.\d+Z$/, 'Z')
}

/** Whether `isoUtc` falls within `windowMinutes` of `centerIsoUtc`. */
export function withinMinutesOf(isoUtc: string, centerIsoUtc: string, windowMinutes: number): boolean {
  const deltaMs = Math.abs(new Date(isoUtc).getTime() - new Date(centerIsoUtc).getTime())
  return deltaMs <= windowMinutes * 60_000
}

/** The item in `items` whose `tsOf(item)` is closest to `targetIsoUtc`
 * (T60: "latest blurred thumbnail at slider time" means nearest, not
 * literally the last item in the list). Returns null for an empty list. */
export function nearestByTime<T>(items: T[], targetIsoUtc: string, tsOf: (item: T) => string): T | null {
  if (items.length === 0) return null
  const targetMs = new Date(targetIsoUtc).getTime()
  let best = items[0]
  let bestDelta = Math.abs(new Date(tsOf(items[0])).getTime() - targetMs)
  for (const item of items.slice(1)) {
    const delta = Math.abs(new Date(tsOf(item)).getTime() - targetMs)
    if (delta < bestDelta) {
      best = item
      bestDelta = delta
    }
  }
  return best
}
