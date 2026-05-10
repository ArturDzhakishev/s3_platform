import { useState, useCallback } from 'react'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'

export function Hosts() {
  const [hosts, setHosts]     = useState([])
  const [loading, setLoading] = useState(true)
  const [pinging, setPinging] = useState({})

  const fetch = useCallback(async () => {
    try { setHosts(await api.hosts.list()) }
    finally { setLoading(false) }
  }, [])

  usePolling(fetch, 10000)

  async function ping(host) {
    setPinging(p => ({ ...p, [host.host_id]: true }))
    try {
      await api.hosts.ping({
        ip: host.ip,
        ssh_user: host.ssh_user,
        ssh_port: host.ssh_port,
        ssh_private_key_path: host.ssh_private_key_path,
      })
      await fetch()
    } catch (e) {
      alert(e.message)
    } finally {
      setPinging(p => ({ ...p, [host.host_id]: false }))
    }
  }

  const hostStatus = s => s === 'in_use' ? 'ready' : s  // переиспользуем badge

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-slide-up">
      <div>
        <h1 className="text-2xl font-semibold text-text">Хосты</h1>
        <p className="text-sm text-muted mt-1">{hosts.length} хостов в инвентаре</p>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-muted text-sm animate-pulse">Загрузка…</div>
        ) : hosts.length === 0 ? (
          <div className="py-16 text-center text-muted text-sm">
            Хостов нет. Они добавляются автоматически при создании кластера.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  {['Хост', 'IP', 'SSH', 'Роль', 'Статус', 'Кластер', ''].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hosts.map(host => (
                  <tr key={host.host_id} className="border-t border-border hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-text">{host.label}</div>
                      <div className="text-xs text-muted font-mono">{host.host_id.slice(0,8)}…</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text">{host.ip}</td>
                    <td className="px-4 py-3 text-xs text-muted font-mono">
                      {host.ssh_user}:{host.ssh_port}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge text-xs ${host.role === 'master' ? 'bg-yellow/10 text-yellow border-yellow/20' : 'bg-white/5 text-muted border-border'}`}>
                        {host.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={host.status === 'in_use' ? 'ready' : host.status} />
                      {host.status === 'in_use' && <span className="text-xs text-muted ml-1">(in use)</span>}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">
                      {host.cluster_id ? host.cluster_id.slice(0,8) + '…' : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => ping(host)}
                        disabled={pinging[host.host_id]}
                        className="btn-ghost text-xs py-1 px-2"
                      >
                        {pinging[host.host_id] ? '…' : 'Ping'}
                      </button>
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
