import { useEffect, useState } from 'react'
import { api } from '../api/client'
import ConfigEditor from '../components/ConfigEditor'

const LABELS: Record<string, string> = {
  child: 'Child Profile',
  pipeline: 'Pipeline',
  research: 'Research',
}

export default function ConfigsPage() {
  const [keys, setKeys] = useState<string[]>([])
  const [active, setActive] = useState<string | null>(null)

  useEffect(() => {
    api.configs.list().then(ks => {
      setKeys(ks)
      if (ks.length > 0) setActive(ks[0])
    })
  }, [])

  const label = (k: string) =>
    LABELS[k] ?? (k.startsWith('section/') ? k.replace('section/', '§ ') : k)

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Tab sidebar */}
      <div style={{ width: 160, borderRight: '1px solid #313244', padding: '16px 0' }}>
        {keys.map(k => (
          <button
            key={k}
            onClick={() => setActive(k)}
            style={{
              display: 'block', width: '100%', textAlign: 'left',
              padding: '8px 12px', border: 'none', cursor: 'pointer',
              background: active === k ? '#313244' : 'transparent',
              color: active === k ? '#cba6f7' : '#cdd6f4',
              fontSize: 13,
            }}
          >
            {label(k)}
          </button>
        ))}
      </div>
      {/* Editor */}
      <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column' }}>
        {active ? <ConfigEditor key={active} fileKey={active} /> : <p>Select a config</p>}
      </div>
    </div>
  )
}
