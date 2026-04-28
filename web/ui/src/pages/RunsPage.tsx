import { useEffect, useState } from 'react'
import { api, type RunSummary, type ModelPresetCatalog } from '../api/client'
import RunList from '../components/RunList'
import RunDetail from '../components/RunDetail'

const PROVIDER_OPTIONS: Record<string, string[]> = {
  research: ['brave_deterministic'],
  ranking: ['heuristic_ranker', 'hosted_model_ranker'],
  synthesis: ['hosted_packet_synthesis', 'hosted_integrated_search'],
  render: ['local_renderer'],
}

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<ModelPresetCatalog | null>(null)

  const refresh = () => api.runs.list().then(setRuns)
  useEffect(() => {
    refresh()
    api.modelPresets().then(setCatalog).catch(e => console.error('preset load failed', e))
  }, [])

  const synthesisStrategy = overrides.synthesis_provider ?? PROVIDER_OPTIONS.synthesis[0]
  const rankingStrategy = overrides.ranking_provider ?? PROVIDER_OPTIONS.ranking[0]

  // Filter presets compatible with the selected synthesis strategy.
  const compatibleSynthesisPresets = (() => {
    if (!catalog) return []
    const requiresTools = catalog.strategy_requirements[synthesisStrategy]?.requires_tools
    return catalog.presets.filter(p => !requiresTools || p.supports_tools)
  })()

  // Ranking model presets — model_ranker has no tool requirement; show all.
  const rankingPresets = catalog?.presets ?? []

  // Auto-correct synthesis_model when the strategy changes and current pick is incompatible.
  useEffect(() => {
    if (!catalog) return
    const current = overrides.synthesis_model
    const stillCompatible = current && compatibleSynthesisPresets.some(p => p.name === current)
    if (!stillCompatible && compatibleSynthesisPresets.length > 0) {
      const fallback = catalog.defaults.synthesis && compatibleSynthesisPresets.some(p => p.name === catalog.defaults.synthesis)
        ? catalog.defaults.synthesis
        : compatibleSynthesisPresets[0].name
      setOverrides(prev => ({ ...prev, synthesis_model: fallback }))
    }
  }, [synthesisStrategy, catalog])

  // Initialize defaults once catalog arrives.
  useEffect(() => {
    if (!catalog) return
    setOverrides(prev => {
      const next = { ...prev }
      if (!next.synthesis_model && catalog.defaults.synthesis) next.synthesis_model = catalog.defaults.synthesis
      if (!next.ranking_model && catalog.defaults.ranking) next.ranking_model = catalog.defaults.ranking
      return next
    })
  }, [catalog])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    setError(null)

    const fullOverrides: Record<string, string> = { ...overrides }
    for (const [stage, opts] of Object.entries(PROVIDER_OPTIONS)) {
      const key = `${stage}_provider`
      if (!fullOverrides[key]) fullOverrides[key] = opts[0]
    }

    // Drop ranking_model when ranking strategy is heuristic (no model used).
    if (fullOverrides.ranking_provider === 'heuristic_ranker') {
      delete fullOverrides.ranking_model
    }

    try {
      await api.runs.create(newName.trim(), fullOverrides)
      setNewName('')
      // Keep current overrides so the next run inherits the same picks.
      await refresh()
      setOpenRun(newName.trim())
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setCreating(false)
    }
  }

  if (openRun) {
    return (
      <div>
        <button onClick={() => { setOpenRun(null); refresh() }} style={{ margin: 12 }}>
          ← Back to runs
        </button>
        <RunDetail runName={openRun} />
      </div>
    )
  }

  const showRankingModel = rankingStrategy === 'hosted_model_ranker'

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginTop: 0 }}>Runs</h2>

      {/* New run form */}
      <div style={{ marginBottom: 24, padding: 16, background: '#11111b', borderRadius: 8 }}>
        <h3 style={{ marginTop: 0, fontSize: 14 }}>New Run</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="run name (e.g. approach-b1)"
            style={{ flex: 1, padding: '6px 10px', background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
          />
          <button onClick={handleCreate} disabled={creating || !newName.trim()}>
            {creating ? 'Creating…' : 'Create'}
          </button>
        </div>

        {/* Strategy row */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: '#6c7086', alignSelf: 'center' }}>Strategy:</span>
          {Object.entries(PROVIDER_OPTIONS).map(([stage, opts]) => (
            <label key={stage} style={{ fontSize: 12, color: '#6c7086' }}>
              {stage}:&nbsp;
              <select
                value={overrides[`${stage}_provider`] ?? opts[0]}
                onChange={e => setOverrides(prev => ({ ...prev, [`${stage}_provider`]: e.target.value }))}
                style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
              >
                {opts.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          ))}
        </div>

        {/* Model row */}
        {catalog && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: '#6c7086' }}>Model:</span>
            {showRankingModel && (
              <label style={{ fontSize: 12, color: '#6c7086' }}>
                ranking:&nbsp;
                <select
                  value={overrides.ranking_model ?? catalog.defaults.ranking ?? ''}
                  onChange={e => setOverrides(prev => ({ ...prev, ranking_model: e.target.value }))}
                  style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
                >
                  {rankingPresets.map(p => <option key={p.name} value={p.name}>{p.label}</option>)}
                </select>
              </label>
            )}
            <label style={{ fontSize: 12, color: '#6c7086' }}>
              synthesis:&nbsp;
              <select
                value={overrides.synthesis_model ?? catalog.defaults.synthesis ?? ''}
                onChange={e => setOverrides(prev => ({ ...prev, synthesis_model: e.target.value }))}
                style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
              >
                {compatibleSynthesisPresets.map(p => <option key={p.name} value={p.name}>{p.label}</option>)}
              </select>
            </label>
            {synthesisStrategy === 'hosted_integrated_search' && (
              <span style={{ fontSize: 11, color: '#a6adc8', fontStyle: 'italic' }}>
                This model also does the search and ranking inline.
              </span>
            )}
          </div>
        )}
        {error && <div style={{ color: '#f38ba8', fontSize: 13, marginTop: 8 }}>{error}</div>}
      </div>

      <RunList runs={runs} onOpen={setOpenRun} />
    </div>
  )
}
