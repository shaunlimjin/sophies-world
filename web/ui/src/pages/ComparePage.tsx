import CompareView from '../components/CompareView'

export default function ComparePage() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <h2 style={{ margin: '0 24px 0', padding: '16px 0', borderBottom: '1px solid #313244' }}>
        Compare Runs
      </h2>
      <div style={{ flex: 1, minHeight: 0 }}>
        <CompareView />
      </div>
    </div>
  )
}
