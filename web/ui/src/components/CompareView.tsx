import { useEffect, useState } from 'react'
import { api, RunSummary, CompareResult } from '../api/client'
import PromoteButton from './PromoteButton'

const STAGES = ['research', 'ranking', 'synthesis', 'render']

export default function CompareView() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [leftRun, setLeftRun] = useState('')
  const [rightRun, setRightRun] = useState('')
  const [stage, setStage] = useState('synthesis')
  const [result, setResult] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { api.runs.list().then(setRuns) }, [])

  useEffect(() => {
    if (!leftRun || !rightRun) { setResult(null); return }
    setLoading(true)
    api.compare(leftRun, rightRun, stage)
      .then(setResult)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [leftRun, rightRun, stage])

  const runOpts = runs.map(r => r.name)
  const promotableRun = leftRun || rightRun
  const promotableRunState = runs.find(r => r.name === promotableRun)
  const synthesisComplete = promotableRunState?.stage_statuses['synthesis'] === 'done'

  const renderArtifact = (content: string | null, side: string) => {
    if (!content) return (
      <div style={{ flex: 1, padding: 12, color: '#6c7086', fontSize: 13 }}>
        Stage not run yet
      </div>
    )
    return stage === 'render' ? (
      <iframe
        key={side}
        srcDoc={content}
        style={{ flex: 1, border: '1px solid #313244', borderRadius: 4 }}
        title={`${side} render`}
      />
    ) : (
      <pre style={{ flex: 1, background: '#11111b', padding: 10, borderRadius: 4,
                    fontSize: 11, overflow: 'auto', color: '#cdd6f4', margin: 0 }}>
        {JSON.stringify(JSON.parse(content), null, 2)}
      </pre>
    )
  }

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={leftRun} onChange={e => setLeftRun(e.target.value)}
          style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4, padding: '6px 10px' }}>
          <option value="">— Left run —</option>
          {runOpts.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
        <select value={rightRun} onChange={e => setRightRun(e.target.value)}
          style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4, padding: '6px 10px' }}>
          <option value="">— Right run —</option>
          {runOpts.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
        <div style={{ display: 'flex', gap: 4 }}>
          {STAGES.map(s => (
            <button key={s} onClick={() => setStage(s)}
              style={{ padding: '6px 12px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: 12,
                       background: stage === s ? '#89b4fa' : '#313244',
                       color: stage === s ? '#1e1e2e' : '#cdd6f4', fontWeight: stage === s ? 700 : 400 }}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Promote */}
      {promotableRun && (
        <PromoteButton runName={promotableRun} synthesisComplete={!!synthesisComplete} />
      )}

      {/* Split panels */}
      {loading && <div style={{ color: '#6c7086', margin: 12 }}>Loading…</div>}
      {result && (
        <div style={{ flex: 1, display: 'flex', gap: 8, marginTop: 12, minHeight: 0 }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, color: '#6c7086', marginBottom: 4 }}>{leftRun || '(none)'}</div>
            {renderArtifact(result.left, 'left')}
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, color: '#6c7086', marginBottom: 4 }}>{rightRun || '(none)'}</div>
            {renderArtifact(result.right, 'right')}
          </div>
        </div>
      )}
    </div>
  )
}
