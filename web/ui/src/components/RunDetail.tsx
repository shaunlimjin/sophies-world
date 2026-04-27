import { useEffect, useRef, useState } from 'react'
import { api, type RunState } from '../api/client'
import StagePanel from './StagePanel'
import ArtifactDetail from './ArtifactDetail'

interface Props { runName: string }

const STAGE_ORDER = ['research', 'ranking', 'synthesis', 'render']

export default function RunDetail({ runName }: Props) {
  const [runState, setRunState] = useState<RunState | null>(null)
  const [activeStage, setActiveStage] = useState('research')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchState = () =>
    api.runs.get(runName).then(setRunState).catch(console.error)

  useEffect(() => {
    fetchState()
    pollRef.current = setInterval(fetchState, 3000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [runName])

  const triggerStage = async (stage: string) => {
    try {
      await api.runs.triggerStage(runName, stage)
      await fetchState()
    } catch (e: unknown) {
      alert((e as Error).message)
    }
  }

  const handleRunAll = async () => {
    for (const stage of STAGE_ORDER) {
      await triggerStage(stage)
      await waitForStage(stage)
    }
    await fetchState()
  }

  const waitForStage = (stage: string): Promise<void> => {
    return new Promise(resolve => {
      const interval = setInterval(async () => {
        const state = await api.runs.get(runName)
        const s = state.stages.find(x => x.name === stage)
        if (s && (s.status === 'done' || s.status === 'failed')) {
          clearInterval(interval)
          setRunState(state)
          resolve()
        }
      }, 2000)
    })
  }

  if (!runState) return <div style={{ padding: 24 }}>Loading…</div>

  const activeStageState = runState.stages.find(s => s.name === activeStage)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {runState.settings && Object.keys(runState.settings).length > 0 && (
        <div style={{ padding: '0 24px 12px', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: '#6c7086' }}>Settings:</span>
          {Object.entries(runState.settings).map(([k, v]) => (
            <span key={k} style={{ fontSize: 11, background: '#313244', color: '#a6adc8', padding: '2px 8px', borderRadius: 4 }}>
              {k}: {v}
            </span>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <StagePanel
          stages={runState.stages}
          active={activeStage}
          onSelect={setActiveStage}
          onRunAll={handleRunAll}
          onRerun={triggerStage}
        />
        {activeStageState && (
          <ArtifactDetail
            key={`${runName}-${activeStage}`}
            runName={runName}
            stage={activeStage}
            status={activeStageState.status}
          />
        )}
      </div>
    </div>
  )
}