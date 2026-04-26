interface Props { runName: string }
export default function RunDetail({ runName }: Props) {
  return <div style={{ padding: 24 }}>Run: {runName} (detail loading…)</div>
}