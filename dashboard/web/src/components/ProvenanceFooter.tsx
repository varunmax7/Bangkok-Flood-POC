interface ProvenanceFooterProps {
  dataClass?: string | null
  modelVersion?: string | null
  runId?: string | null
}

/** Always visible, per Agent rule 11: every screen states the feasibility caveat. */
export function ProvenanceFooter({ dataClass, modelVersion, runId }: ProvenanceFooterProps) {
  return (
    <footer className="provenance-footer">
      <span>{dataClass ?? '—'}</span>
      <span aria-hidden="true">&middot;</span>
      <span>{modelVersion ?? '—'}</span>
      <span aria-hidden="true">&middot;</span>
      <span>{runId ?? '—'}</span>
      <span className="warning">Feasibility prototype &mdash; not for flood warning</span>
    </footer>
  )
}
