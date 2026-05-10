import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'
import { EngineBadge } from '../components/EngineBadge'

// ── Stat card ──────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }) {
  const accents = {
    blue:   'border-blue/30 bg-blue/5',
    green:  'border-green/30 bg-green/5',
    yellow: 'border-yellow/30 bg-yellow/5',
    red:    'border-red/30 bg-red/5',
  }
  return (
    <div className={`card p-5 border ${accents[accent] || 'border-border'}`}>
      <div className="text-xs font-medium text-muted uppercase tracking-wider mb-3">{label}</div>
      <div className="text-3xl font-semibold text-text font-mono">{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  )
}

// ── Cluster row ────────────────────────────────────────────────────────────
function ClusterRow({ cluster, onDelete }) {
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    if (!confirm(`Удалить кластер ${cluster.name}?`)) return
    setDeleting(true)
    try {
      await api.clusters.delete(cluster.cluster_id)
    } catch (e) {
      alert(e.message)
      setDeleting(false)
    }
  }

  const ts = new Date(cluster.created_at).toLocaleDateString('ru-RU', {
    day: '2-digit', month: 'short', year: 'numeric',
  })

  return (
    <tr className="border-t border-border hover:bg-white/[0.02] transition-colors group">
      <td className="px-4 py-3">
        <Link
          to={`/clusters/${cluster.cluster_id}`}
          className="text-sm font-medium text-text hover:text-blue transition-colors"
        >
          {cluster.name}
        </Link>
        <div className="text-xs text-muted font-mono mt-0.5 truncate max-w-[160px]">
          {cluster.cluster_id.slice(0, 8)}…
        </div>
      </td>
      <td className="px-4 py-3">
        <EngineBadge engine={cluster.engine} />
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={cluster.status} />
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-muted font-mono">{cluster.node_count}</span>
      </td>
      <td className="px-4 py-3">
        {cluster.s3_endpoint
          ? <a href={cluster.s3_endpoint} target="_blank" rel="noreferrer"
              className="text-xs font-mono text-blue hover:underline truncate max-w-[160px] block">
              {cluster.s3_endpoint}
            </a>
          : <span className="text-xs text-muted">—</span>
        }
      </td>
      <td className="px-4 py-3 text-xs text-muted">{ts}</td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <Link
            to={`/clusters/${cluster.cluster_id}`}
            className="btn-ghost text-xs py-1 px-2"
          >
            Детали
          </Link>
          <button
            onClick={handleDelete}
            disabled={deleting || cluster.status === 'deleting'}
            className="btn-danger text-xs py-1 px-2"
          >
            {deleting ? '…' : 'Удалить'}
          </button>
        </div>
      </td>
    </tr>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
export function Dashboard() {
  const [clusters, setClusters] = useState([])
  const [jobs, setJobs]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  const [filterEngine, setFilterEngine] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const fetch = useCallback(async () => {
    try {
      const [cls, jbs] = await Promise.all([
        api.clusters.list(),
        api.jobs.list({ limit: 5 }),
      ])
      setClusters(cls)
      setJobs(jbs)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  usePolling(fetch, 5000)

  // Derived stats
  const stats = {
    total:     clusters.length,
    ready:     clusters.filter(c => c.status === 'ready').length,
    failed:    clusters.filter(c => c.status === 'failed').length,
    deploying: clusters.filter(c => ['deploying', 'scaling'].includes(c.status)).length,
  }

  const filtered = clusters.filter(c => {
    if (filterEngine && c.engine !== filterEngine) return false
    if (filterStatus && c.status !== filterStatus) return false
    return true
  })

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-muted text-sm">
      <span className="animate-pulse">Загрузка…</span>
    </div>
  )

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-slide-up">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Dashboard</h1>
          <p className="text-sm text-muted mt-1">Управление S3-совместимыми кластерами</p>
        </div>
        <Link to="/clusters/new" className="btn-primary">
          <span>+</span> Новый кластер
        </Link>
      </div>

      {error && (
        <div className="card p-4 border-red/30 bg-red/5 text-red text-sm">
          Ошибка подключения к API: {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Всего кластеров" value={stats.total}     accent="blue"   />
        <StatCard label="Активных"        value={stats.ready}     accent="green"  sub="статус ready" />
        <StatCard label="В процессе"      value={stats.deploying} accent="yellow" sub="deploy / scale" />
        <StatCard label="С ошибкой"       value={stats.failed}    accent="red"    />
      </div>

      {/* Clusters table */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Кластеры</h2>
          <div className="flex items-center gap-3">
            <select
              value={filterEngine}
              onChange={e => setFilterEngine(e.target.value)}
              className="input py-1 text-xs w-36"
            >
              <option value="">Все движки</option>
              <option value="ceph">Ceph</option>
              <option value="seaweedfs">SeaweedFS</option>
              <option value="garage">Garage</option>
            </select>
            <select
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
              className="input py-1 text-xs w-36"
            >
              <option value="">Все статусы</option>
              <option value="deploying">deploying</option>
              <option value="ready">ready</option>
              <option value="scaling">scaling</option>
              <option value="deleting">deleting</option>
              <option value="failed">failed</option>
            </select>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="py-16 text-center text-muted text-sm">
            {clusters.length === 0
              ? <>Кластеров нет. <Link to="/clusters/new" className="text-blue hover:underline">Создать первый</Link></>
              : 'Нет кластеров по выбранным фильтрам'
            }
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left">
                  {['Имя', 'Движок', 'Статус', 'Ноды', 'S3 Endpoint', 'Создан', ''].map(h => (
                    <th key={h} className="px-4 py-2.5 text-xs font-medium text-muted uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <ClusterRow key={c.cluster_id} cluster={c} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent jobs */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Последние задачи</h2>
          <Link to="/jobs" className="text-xs text-muted hover:text-text transition-colors">
            Все задачи →
          </Link>
        </div>
        {jobs.length === 0 ? (
          <div className="py-10 text-center text-muted text-sm">Задач нет</div>
        ) : (
          <div className="divide-y divide-border">
            {jobs.map(job => (
              <div key={job.job_id} className="flex items-center gap-4 px-5 py-3 hover:bg-white/[0.02] transition-colors">
                <StatusBadge status={job.status} type="job" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text font-mono truncate">{job.playbook}</div>
                  <div className="text-xs text-muted mt-0.5 font-mono">{job.job_id.slice(0, 8)}…</div>
                </div>
                <div className="text-xs text-muted shrink-0">
                  {new Date(job.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                </div>
                <Link to={`/jobs/${job.job_id}`} className="text-xs text-blue hover:underline shrink-0">
                  Лог →
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
