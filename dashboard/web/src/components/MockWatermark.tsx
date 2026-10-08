export function MockWatermark({ active }: { active: boolean }) {
  if (!active) return null
  return (
    <div className="mock-watermark" aria-label="mock data warning">
      MOCK
    </div>
  )
}
