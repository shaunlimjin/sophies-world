import { useState } from 'react'
import { api } from '../api/client'

interface Props {
  runName: string
  synthesisComplete: boolean
}

export default function PromoteButton({ runName, synthesisComplete }: Props) {
  const [preview, setPreview] = useState<object | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  if (!synthesisComplete) return null

  const handlePreview = async () => {
    setLoading(true)
    setMessage(null)
    try {
      const result = await api.runs.promotePreview(runName, 'staging')
      setPreview(result)
    } catch (e: unknown) {
      setMessage((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    setLoading(true)
    try {
      const result = await api.runs.promoteApply(runName, 'staging')
      setPreview(null)
      setMessage(`Promoted to staging: ${result.copied_to}`)
    } catch (e: unknown) {
      setMessage((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      {!preview ? (
        <button onClick={handlePreview} disabled={loading} style={{ background: '#cba6f7', color: '#1e1e2e', border: 'none', borderRadius: 4, padding: '6px 14px', cursor: 'pointer', fontWeight: 600 }}>
          {loading ? '…' : `Promote ${runName} → Staging`}
        </button>
      ) : (
        <div style={{ background: '#11111b', borderRadius: 6, padding: 12, fontSize: 13 }}>
          <pre style={{ margin: '0 0 8px', color: '#cdd6f4', overflow: 'auto' }}>
            {JSON.stringify(preview, null, 2)}
          </pre>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleApply} disabled={loading} style={{ background: '#a6e3a1', color: '#1e1e2e', border: 'none', borderRadius: 4, padding: '6px 14px', cursor: 'pointer', fontWeight: 600 }}>
              Confirm
            </button>
            <button onClick={() => setPreview(null)} style={{ background: '#45475a', color: '#cdd6f4', border: 'none', borderRadius: 4, padding: '6px 14px', cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {message && <div style={{ color: '#a6e3a1', fontSize: 13, marginTop: 6 }}>{message}</div>}
    </div>
  )
}
