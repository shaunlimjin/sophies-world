// Shared types
export type StageStatus = 'pending' | 'running' | 'done' | 'failed'

export interface StageState {
  name: string
  status: StageStatus
  artifact_path: string | null
}

export interface RunState {
  name: string
  created_at: string
  stages: StageState[]
  settings?: Record<string, string>
}

export interface RunSummary {
  name: string
  created_at: string
  stage_statuses: Record<string, string>
  settings?: Record<string, string>
}

export interface SSEEvent {
  type: 'stage' | 'line' | 'artifact' | 'done' | 'error'
  text?: string
  stage?: string
  status?: string
  success?: boolean
  message?: string
  path?: string
}

export interface CompareResult {
  left: string | null
  right: string | null
  stage: string
  runs: { a: string; b: string }
}

// API helpers
const base = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(base + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(detail.detail ?? resp.statusText)
  }
  return resp.json()
}

// Configs
export const api = {
  configs: {
    list: () => request<string[]>('/configs'),
    get: (key: string) => request<{ content: string }>(`/configs/${key}`),
    put: (key: string, content: string) =>
      request<{ ok: boolean }>(`/configs/${key}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      }),
  },
  runs: {
    list: () => request<RunSummary[]>('/runs'),
    create: (name: string, provider_overrides?: Record<string, string>) =>
      request<RunSummary>('/runs', {
        method: 'POST',
        body: JSON.stringify({ name, provider_overrides: provider_overrides ?? {} }),
      }),
    get: (name: string) => request<RunState>(`/runs/${name}`),
    triggerStage: (name: string, stage: string, overrides?: Record<string, string>) =>
      request<{ accepted: boolean }>(`/runs/${name}/stages/${stage}`, {
        method: 'POST',
        body: JSON.stringify({ provider_overrides: overrides ?? {} }),
      }),
    getArtifact: (name: string, stage: string) =>
      fetch(base + `/runs/${name}/stages/${stage}/artifact`).then(r => r.text()),
    promotePreview: (name: string, to: string) =>
      request<{ run: string; to: string; changes: object[] }>(`/runs/${name}/promote/preview`, {
        method: 'POST',
        body: JSON.stringify({ to }),
      }),
    promoteApply: (name: string, to: string) =>
      request<{ ok: boolean; copied_to: string }>(`/runs/${name}/promote/apply`, {
        method: 'POST',
        body: JSON.stringify({ to, confirmed: true }),
      }),
  },
  compare: (a: string, b: string, stage: string) =>
    request<CompareResult>(`/compare?a=${a}&b=${b}&stage=${stage}`),
}

// SSE hook helper — returns event source URL for a running stage stream
export function stageStreamUrl(runName: string, stage: string): string {
  return `/api/runs/${runName}/stages/${stage}/stream`
}

import { useEffect, useRef, useState } from 'react'

export function useSSE(url: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [isDone, setIsDone] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!url) return
    setEvents([])
    setIsDone(false)
    const es = new EventSource(url)
    esRef.current = es

    const handleEvent = (e: MessageEvent) => {
      const data = JSON.parse(e.data) as SSEEvent
      setEvents(prev => [...prev, data])
      if (data.type === 'done' || data.type === 'error') {
        setIsDone(true)
        es.close()
      }
    }

    ;['stage', 'line', 'artifact', 'done', 'error'].forEach(t =>
      es.addEventListener(t, handleEvent)
    )

    return () => es.close()
  }, [url])

  return { events, isDone }
}
