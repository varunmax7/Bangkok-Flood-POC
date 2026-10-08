import { useAppStore } from '../store'

export function OodBanner() {
  const oodFlag = useAppStore((s) => s.oodFlag)
  if (!oodFlag) return null
  return <div className="ood-banner">Outside training envelope &mdash; run hydraulic model</div>
}
