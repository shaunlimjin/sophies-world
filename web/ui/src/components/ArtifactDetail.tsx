import { useEffect, useState } from 'react'
import { api, useSSE, stageStreamUrl, type SSEEvent, type StageStatus } from '../api/client'

interface Props {
  runName: string
  stage: string
  status: StageStatus
}

export default function ArtifactDetail({ runName, stage, status }: Props) {
  const [streamUrl, setStreamUrl] = useState<string | null>(null)
  const [artifact, setArtifact] = useState<string | null>(null)
  const { events, isDone } = useSSE(streamUrl)

  // When status goes to running (after trigger), connect to stream
  useEffect(() => {
    if (status === 'running') {
      setStreamUrl(stageStreamUrl(runName, stage))
      setArtifact(null)
    }
  }, [runName, stage, status])

  // When stream completes, load artifact
  useEffect(() => {
    if (isDone) {
      setStreamUrl(null)
      api.runs.getArtifact(runName, stage).then(setArtifact).catch(() => {})
    }
  }, [isDone, runName, stage])

  // Load artifact if stage is already done
  useEffect(() => {
    if (status === 'done') {
      api.runs.getArtifact(runName, stage).then(setArtifact).catch(() => {})
    }
  }, [runName, stage, status])

  const logLines = events.filter((e): e is SSEEvent & { text: string } =>
    e.type === 'line' && typeof e.text === 'string'
  )
  const isCached = logLines.some(e => e.text?.includes('cached research packet valid'))

  return (
    <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 13, color: '#6c7086', textTransform: 'capitalize' }}>
          {stage}
        </span>
        {isCached && (
          <span style={{ fontSize: 11, background: '#45475a', color: '#cba6f7',
                         borderRadius: 10, padding: '2px 8px' }}>
            Using cached research
          </span>
        )}
      </div>

      {/* Live log */}
      {(status === 'running' || logLines.length > 0) && (
        <pre style={{ background: '#11111b', padding: 10, borderRadius: 4,
                      fontSize: 12, maxHeight: 200, overflow: 'auto',
                      color: '#a6e3a1', margin: 0 }}>
          {logLines.map((e, i) => <div key={i}>{e.text}</div>)}
          {status === 'running' && !isDone && <div style={{ opacity: 0.5 }}>…</div>}
        </pre>
      )}

      {/* Artifact viewer */}
      {artifact && (
        stage === 'render' ? (
          <iframe
            srcDoc={artifact}
            style={{ flex: 1, border: '1px solid #313244', borderRadius: 4, minHeight: '80vh' }}
            title="Rendered newsletter"
          />
        ) : (
          <pre style={{ flex: 1, background: '#11111b', padding: 12, borderRadius: 4,
                        fontSize: 12, overflow: 'auto', color: '#cdd6f4', margin: 0, textAlign: 'left' }}>
            {JSON.stringify(JSON.parse(artifact), null, 2)}
          </pre>
        )
      )}

      {status === 'failed' && !artifact && (
        <div style={{ color: '#f38ba8', fontSize: 13 }}>Stage failed. Check logs above.</div>
      )}
    </div>
  )
}