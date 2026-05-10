import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'

export function Jobs() {
  const [jobs, setJobs]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [filterStatus, setFilterStatus] = useState('')

  const fetch = useCallback(async () => {
    try {
      const params = filterStatus ? { status: filterStatus } : {}
      setJobs(await api.jobs.list({ ...params, limit: 100 }))
    } finally {
      setLoading(false)
    }
  }, [filterStatus])

  usePolling(fetch, 5000)

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Задачи</h1>
          <p className="text-sm text-muted mt-1">{jobs.length} записей</p>
        </div>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="input py-1 text-xs w-36"
        >
          <option value="">Все статусы</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="success">success</option>
          <option value="failed">failed</option>
        </select>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-muted text-sm animate-pulse">Загрузка…</div>
        ) : jobs.length === 0 ? (
          <div className="py-16 text-center text-muted text-sm">Задач нет</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  {['Задача', 'Статус', 'Тип', 'Плейбук', 'Создана', 'Завершена', ''].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.job_id} className="border-t border-border hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-mono text-xs text-muted">{job.job_id.slice(0, 8)}…</div>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={job.status} type="job" /></td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-muted">{job.job_type}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-text">{job.playbook}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">
                      {new Date(job.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">
                      {job.finished_at ? new Date(job.finished_at).toLocaleString('ru-RU') : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/jobs/${job.job_id}`} className="text-xs text-blue hover:underline">
                        Лог →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
