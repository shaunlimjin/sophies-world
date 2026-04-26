import { StageState } from '../api/client'

const ICON: Record<string, string> = { done: '✓', running: '▶', failed: '✗', pending: '○' }
const COLOR: Record<string, string> = {
  done: '#a6e3a1', running: '#89b4fa', failed: '#f38ba8', pending: '#6c7086',
}

interface Props {
  stages: StageState[]
  active: string
  onSelect: (name: string) => void
  onRunAll: () => void
  onRerun: (stage: string) => void
}

export default function StagePanel({ stages, active, onSelect, onRunAll, onRerun }: Props) {
  const isAnyRunning = stages.some(s => s.status === 'running')
  return (
    <div style={{ width: 200, borderRight: '1px solid #313244', padding: 12 }}>
      <button
        onClick={onRunAll}
        disabled={isAnyRunning}
        style={{ width: '100%', marginBottom: 16, padding: '8px 0',
                 background: '#89b4fa', color: '#1e1e2e', border: 'none',
                 borderRadius: 4, cursor: isAnyRunning ? 'not-allowed' : 'pointer',
                 fontWeight: 600 }}
      >
        {isAnyRunning ? 'Running…' : '▶ Run All'}
      </button>
      {stages.map(s => (
        <div
          key={s.name}
          onClick={() => onSelect(s.name)}
          style={{
            padding: '10px 8px', borderRadius: 4, cursor: 'pointer', marginBottom: 2,
            background: active === s.name ? '#313244' : 'transparent',
            display: 'flex', alignItems: 'center', gap: 8,
          }}
        >
          <span style={{ color: COLOR[s.status], fontSize: 16 }}>{ICON[s.status]}</span>
          <span style={{ flex: 1, fontSize: 14, textTransform: 'capitalize' }}>{s.name}</span>
          {(s.status === 'done' || s.status === 'failed') && (
            <button
              onClick={e => { e.stopPropagation(); onRerun(s.name) }}
              title="Re-run"
              style={{ fontSize: 11, padding: '2px 6px', background: '#45475a',
                       color: '#cdd6f4', border: 'none', borderRadius: 3, cursor: 'pointer' }}
            >
              ↺
            </button>
          )}
        </div>
      ))}
    </div>
  )
}