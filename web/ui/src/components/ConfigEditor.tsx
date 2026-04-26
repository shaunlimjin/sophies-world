import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props {
  fileKey: string
}

export default function ConfigEditor({ fileKey }: Props) {
  const [content, setContent] = useState('')
  const [saved, setSaved] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.configs.get(fileKey).then(r => {
      setContent(r.content)
      setSaved(r.content)
      setError(null)
    }).catch(e => setError(e.message))
  }, [fileKey])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.configs.put(fileKey, content)
      setSaved(content)
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 8, padding: '8px 0' }}>
        <button onClick={handleSave} disabled={saving || content === saved}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={() => { setContent(saved); setError(null) }} disabled={content === saved}>
          Discard
        </button>
      </div>
      {error && (
        <div style={{ color: '#f38ba8', fontSize: 13, padding: '4px 0' }}>{error}</div>
      )}
      <textarea
        value={content}
        onChange={e => setContent(e.target.value)}
        style={{
          flex: 1, fontFamily: 'monospace', fontSize: 13,
          background: '#11111b', color: '#cdd6f4', border: '1px solid #313244',
          borderRadius: 4, padding: 12, resize: 'none',
        }}
      />
    </div>
  )
}
