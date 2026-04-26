import type { RunSummary } from '../api/client'

const STATUS_ICON: Record<string, string> = {
  done: '✓', running: '▶', failed: '✗', pending: '○',
}
const STATUS_COLOR: Record<string, string> = {
  done: '#a6e3a1', running: '#89b4fa', failed: '#f38ba8', pending: '#6c7086',
}

interface Props {
  runs: RunSummary[]
  onOpen: (name: string) => void
}

export default function RunList({ runs, onOpen }: Props) {
  if (runs.length === 0) {
    return <p style={{ color: '#6c7086' }}>No runs yet. Create one above.</p>
  }
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
      <thead>
        <tr style={{ borderBottom: '1px solid #313244', color: '#6c7086' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px' }}>Name</th>
          <th style={{ textAlign: 'left', padding: '6px 8px' }}>Stages</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {runs.map(run => (
          <tr key={run.name} style={{ borderBottom: '1px solid #1e1e2e' }}>
            <td style={{ padding: '8px' }}>{run.name}</td>
            <td style={{ padding: '8px' }}>
              {['research', 'ranking', 'synthesis', 'render'].map(s => {
                const status = run.stage_statuses[s] ?? 'pending'
                return (
                  <span
                    key={s}
                    title={`${s}: ${status}`}
                    style={{ color: STATUS_COLOR[status], marginRight: 6, fontSize: 16 }}
                  >
                    {STATUS_ICON[status]}
                  </span>
                )
              })}
            </td>
            <td style={{ padding: '8px' }}>
              <button onClick={() => onOpen(run.name)} style={{ fontSize: 12 }}>Open</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}