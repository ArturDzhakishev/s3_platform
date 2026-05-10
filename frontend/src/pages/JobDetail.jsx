import { useState, useCallback, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'

export function JobDetail() {
  const { id } = useParams()
  const [job, setJob]         = useState(null)
  const [loading, setLoading] = useState(true)
  const [autoScroll, setAutoScroll] = useState(true)
  const logRef = useRef(null)

  const isActive = job && ['pending', 'running'].includes(job.status)

  const fetch = useCallback(async () => {
    try {
      setJob(await api.jobs.get(id))
    } finally {
      setLoading(false)
    }
  }, [id])

  usePolling(fetch, 3000, isActive)

  // Однократно при первом маунте
  useEffect(() => { fetch() }, [fetch])

  // Auto-scroll лога вниз
  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [job?.log, autoScroll])

  if (loading) return <div className="flex items-center justify-center h-64 text-muted text-sm animate-pulse">Загрузка…</div>
  if (!job) return <div className="text-muted text-sm">Задача не найдена. <Link to="/jobs" className="text-blue hover:underline">Назад</Link></div>

  const duration = job.finished_at && job.started_at
    ? Math.round((new Date(job.finished_at) - new Date(job.started_at)) / 1000)
    : null

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-slide-up">
      <div className="flex items-center gap-3">
        <Link to="/jobs" className="text-muted hover:text-text transition-colors text-sm">← Задачи</Link>
        <span className="text-border">/</span>
        <span className="font-mono text-sm text-text">{id.slice(0, 8)}…</span>
        <StatusBadge status={job.status} type="job" />
        {isActive && <span className="text-xs text-muted animate-pulse">обновляется каждые 3 сек</span>}
      </div>

      {/* Meta */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">Тип</div>
          <div className="text-sm font-mono text-text">{job.job_type}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">Плейбук</div>
          <div className="text-sm font-mono text-text">{job.playbook}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">Код возврата</div>
          <div className={`text-lg font-mono font-semibold ${job.return_code === 0 ? 'text-green' : job.return_code === null ? 'text-muted' : 'text-red'}`}>
            {job.return_code ?? '—'}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">Длительность</div>
          <div className="text-sm font-mono text-text">{duration ? `${duration}с` : '—'}</div>
        </div>
      </div>

      {/* Cluster link */}
      <div className="card p-4 flex items-center gap-3">
        <span className="text-xs text-muted uppercase tracking-wider">Кластер:</span>
        <Link to={`/clusters/${job.cluster_id}`} className="text-sm font-mono text-blue hover:underline">
          {job.cluster_id}
        </Link>
      </div>

      {/* Log */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <span className="text-xs font-medium text-muted uppercase tracking-wider">Лог Ansible</span>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
              <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)}
                className="accent-blue" />
              Auto-scroll
            </label>
            {job.log && (
              <button
                onClick={() => navigator.clipboard.writeText(job.log)}
                className="text-xs text-muted hover:text-text transition-colors"
              >
                Скопировать
              </button>
            )}
          </div>
        </div>
        <div
          ref={logRef}
          className="h-[480px] overflow-y-auto p-4 font-mono text-xs leading-relaxed text-muted bg-bg"
        >
          {job.log
            ? job.log.split('\n').map((line, i) => {
                const isOk      = line.includes('ok:') || line.includes('changed:')
                const isFail    = line.includes('FAILED') || line.includes('failed:') || line.includes('ERROR')
                const isPlay    = line.startsWith('PLAY ')
                const isTask    = line.startsWith('TASK ')
                const isRecap   = line.includes('PLAY RECAP')
                return (
                  <div key={i} className={
                    isRecap  ? 'text-yellow font-medium mt-2' :
                    isPlay   ? 'text-blue font-medium mt-3' :
                    isTask   ? 'text-purple mt-2' :
                    isFail   ? 'text-red' :
                    isOk     ? 'text-green' :
                    'text-muted'
                  }>
                    {line || '\u00a0'}
                  </div>
                )
              })
            : <span className="text-muted">
                {isActive ? 'Ожидание вывода…' : 'Лог пуст'}
              </span>
          }
        </div>
      </div>
    </div>
  )
}
