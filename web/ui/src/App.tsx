import { useState } from 'react'
import ConfigsPage from './pages/ConfigsPage'
import RunsPage from './pages/RunsPage'
import ComparePage from './pages/ComparePage'

type Page = 'configs' | 'runs' | 'compare'

export default function App() {
  const [page, setPage] = useState<Page>('runs')

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Sidebar */}
      <nav style={{
        width: 180, background: '#1e1e2e', color: '#cdd6f4',
        display: 'flex', flexDirection: 'column', padding: '24px 0',
      }}>
        <div style={{ padding: '0 16px 24px', fontWeight: 700, fontSize: 14, color: '#89b4fa' }}>
          Sophie's World
        </div>
        {(['runs', 'configs', 'compare'] as Page[]).map(p => (
          <button
            key={p}
            onClick={() => setPage(p)}
            style={{
              background: page === p ? '#313244' : 'transparent',
              color: page === p ? '#cba6f7' : '#cdd6f4',
              border: 'none', textAlign: 'left', padding: '10px 16px',
              cursor: 'pointer', fontSize: 14, textTransform: 'capitalize',
            }}
          >
            {p === 'runs' ? '▶ Runs' : p === 'configs' ? '⚙ Configs' : '⇄ Compare'}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto', background: '#1a1a2e', color: '#e2e8f0' }}>
        {page === 'configs' && <ConfigsPage />}
        {page === 'runs' && <RunsPage />}
        {page === 'compare' && <ComparePage />}
      </main>
    </div>
  )
}
