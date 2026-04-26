import { useEffect, useState } from 'react'
import { api, RunSummary } from '../api/client'
import RunList from '../components/RunList'
import RunDetail from '../components/RunDetail'

const PROVIDER_OPTIONS = {
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

  const refresh = () => api.runs.list().then(setRuns)
  useEffect(() => { refresh() }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    setError(null)
    try {
      await api.runs.create(newName.trim(), overrides)
      setNewName('')
      setOverrides({})
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
        {/* Provider overrides */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
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
        {error && <div style={{ color: '#f38ba8', fontSize: 13, marginTop: 8 }}>{error}</div>}
      </div>

      <RunList runs={runs} onOpen={setOpenRun} />
    </div>
  )
}