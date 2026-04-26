import { useEffect, useRef, useState } from 'react'
import { api, RunState } from '../api/client'
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
    <div style={{ display: 'flex', height: '100%' }}>
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
  )
}