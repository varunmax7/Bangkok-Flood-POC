import { useEffect, useState } from 'react'
import { api, type CctvObservation } from '../api'
import { fmtICT } from '../time'

interface CameraPanelProps {
  camId: string
  onClose: () => void
}

export function CameraPanel({ camId, onClose }: CameraPanelProps) {
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

  const latest = items[items.length - 1]

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>{camId}</h3>
        <button type="button" onClick={onClose} aria-label="close">
          &times;
        </button>
      </div>
      {latest ? (
        <>
          <img src={latest.thumb_url} alt={camId} className="camera-thumb" />
          <p>
            <span className="badge">{latest.class_smoothed ?? latest.class}</span>
            <span className="muted"> visual flood severity proxy &middot; {fmtICT(latest.ts_utc)}</span>
          </p>
        </>
      ) : (
        <p className="muted">{gap ?? 'Loading…'}</p>
      )}
    </div>
  )
}
