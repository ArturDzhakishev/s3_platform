const CLUSTER_STYLES = {
  ready:     'bg-green/10 text-green border border-green/20',
  deploying: 'bg-blue/10 text-blue border border-blue/20',
  scaling:   'bg-purple/10 text-purple border border-purple/20',
  deleting:  'bg-yellow/10 text-yellow border border-yellow/20',
  failed:    'bg-red/10 text-red border border-red/20',
}

const JOB_STYLES = {
  success: 'bg-green/10 text-green border border-green/20',
  running: 'bg-blue/10 text-blue border border-blue/20',
  pending: 'bg-yellow/10 text-yellow border border-yellow/20',
  failed:  'bg-red/10 text-red border border-red/20',
}

const DOTS = {
  ready:     'bg-green',
  deploying: 'bg-blue animate-pulse',
  scaling:   'bg-purple animate-pulse',
  deleting:  'bg-yellow animate-pulse',
  failed:    'bg-red',
  success:   'bg-green',
  running:   'bg-blue animate-pulse',
  pending:   'bg-yellow animate-pulse',
}

export function StatusBadge({ status, type = 'cluster' }) {
  const styles = type === 'job' ? JOB_STYLES : CLUSTER_STYLES
  const cls = styles[status] || 'bg-white/5 text-muted border border-border'
  const dot = DOTS[status] || 'bg-muted'

  return (
    <span className={`badge ${cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  )
}
