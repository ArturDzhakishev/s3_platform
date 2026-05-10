const STYLES = {
  ceph:      'bg-orange-500/10 text-orange-400 border border-orange-500/20',
  seaweedfs: 'bg-teal-500/10 text-teal-400 border border-teal-500/20',
  garage:    'bg-violet-500/10 text-violet-400 border border-violet-500/20',
}

const ICONS = {
  ceph:      '⬡',
  seaweedfs: '◈',
  garage:    '◻',
}

export function EngineBadge({ engine }) {
  const cls = STYLES[engine] || 'bg-white/5 text-muted border border-border'
  return (
    <span className={`badge ${cls}`}>
      <span>{ICONS[engine] || '●'}</span>
      {engine}
    </span>
  )
}
