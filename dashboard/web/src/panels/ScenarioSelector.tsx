import { useEffect, useState } from 'react'
import { api, type ScenarioSummary } from '../api'
import { useAppStore } from '../store'

const SPLIT_ORDER = ['TRAIN', 'VAL', 'TEST', 'TEST_OOD']

export function ScenarioSelector() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const scenarioId = useAppStore((s) => s.scenarioId)
  const setScenarioId = useAppStore((s) => s.setScenarioId)

  useEffect(() => {
    api
      .scenarios(true)
      .then(setScenarios)
      .catch(() => setScenarios([]))
  }, [])

  useEffect(() => {
    if (!scenarioId && scenarios.length > 0) setScenarioId(scenarios[0].scenario_id)
  }, [scenarios, scenarioId, setScenarioId])

  const grouped = SPLIT_ORDER.map((split) => ({
    split,
    items: scenarios.filter((s) => (s.split ?? 'TRAIN') === split),
  })).filter((g) => g.items.length > 0)

  return (
    <div className="panel">
      <h3>Scenario</h3>
      {grouped.map((g) => (
        <div key={g.split} className="scenario-group">
          <div className="split-label">{g.split}</div>
          {g.items.map((s) => (
            <button
              key={s.scenario_id}
              type="button"
              className={`scenario-item ${s.scenario_id === scenarioId ? 'active' : ''}`}
              onClick={() => setScenarioId(s.scenario_id)}
            >
              {s.name ?? s.scenario_id}
              {s.data_class_summary && <span className="badge">{s.data_class_summary}</span>}
              {s.is_mock && <span className="badge badge-mock">MOCK</span>}
            </button>
          ))}
        </div>
      ))}
      {scenarios.length === 0 && <p className="muted">No scenarios found — run `make fixtures`.</p>}
    </div>
  )
}
