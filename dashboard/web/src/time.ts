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
