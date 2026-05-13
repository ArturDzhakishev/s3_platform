import { useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'
import { EngineBadge } from '../components/EngineBadge'

function emptyHost() {
  return {
    label: '', ip: '', ssh_user: 'user', ssh_port: 22,
    ssh_private_key: '',
    role: 'worker', groups: [], zone: 'zone1', capacity: '1G',
    _keyMode: 'paste',
  }
}

// ── SSH key selector (переиспользуемый) ───────────────────────────────────
function SshKeyField({ host, onChange }) {
  const fileRef = useRef(null)

  function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => onChange('ssh_private_key', ev.target.result)
    reader.readAsText(file)
    onChange('_keyMode', 'file')
  }

  return (
    <div>
      <div className="flex items-center gap-1 mb-2">
        <span className="label mb-0">SSH ключ</span>
        <div className="ml-2 flex rounded overflow-hidden border border-border text-xs">
          {[['paste', 'Вставить'], ['file', 'Файл']].map(([mode, label]) => (
            <button key={mode} type="button"
              onClick={() => onChange('_keyMode', mode)}
              className={`px-2.5 py-1 transition-colors ${
                host._keyMode === mode
                  ? 'bg-blue/20 text-blue'
                  : 'text-muted hover:text-text hover:bg-white/5'
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {host._keyMode === 'path' && (
        <input className="input text-xs font-mono"
          placeholder="/home/user/.ssh/id_rsa"
          value={host.ssh_private_key_path}
          onChange={e => onChange('ssh_private_key_path', e.target.value)} />
      )}

      {host._keyMode === 'paste' && (
        <textarea className="input text-xs font-mono" rows={4}
          placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"}
          value={host.ssh_private_key}
          onChange={e => onChange('ssh_private_key', e.target.value)} />
      )}

      {host._keyMode === 'file' && (
        <div className="flex items-center gap-3">
          <button type="button"
            onClick={() => fileRef.current?.click()}
            className="btn-ghost text-xs border border-border">
            📎 Выбрать файл ключа
          </button>
          {host.ssh_private_key
            ? <span className="text-xs text-green">✓ Ключ загружен ({host.ssh_private_key.length} байт)</span>
            : <span className="text-xs text-muted">Файл не выбран</span>
          }
          <input ref={fileRef} type="file" className="hidden"
            accept="*" onChange={handleFile} />
        </div>
      )}
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────

// ── Credentials card ──────────────────────────────────────────────────────
function CredentialsCard({ credentials, engine }) {
  const [visible, setVisible] = useState({})

  function toggle(key) {
    setVisible(v => ({ ...v, [key]: !v[key] }))
  }

  function copy(val) {
    navigator.clipboard.writeText(val)
  }

  // Определить какие поля показывать по движку
  const fields = engine === 'ceph'
    ? [
        { key: 'user',       label: 'Пользователь' },
        { key: 'access_key', label: 'Access Key',  secret: false },
        { key: 'secret_key', label: 'Secret Key',  secret: true  },
      ]
    : engine === 'seaweedfs'
    ? [
        { key: 'user',        label: 'Пользователь' },
        { key: 'access_key',  label: 'Access Key',  secret: false },
        { key: 'secret_key',  label: 'Secret Key',  secret: true  },
        { key: 's3_endpoint', label: 'S3 Endpoint', secret: false },
        { key: 'actions',     label: 'Права',       secret: false },
      ]
    : [
        { key: 'access_key', label: 'Access Key', secret: false },
        { key: 'secret_key', label: 'Secret Key', secret: true  },
      ]

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-3">
        <h2 className="text-sm font-semibold text-text">Ключи доступа S3</h2>
        <span className="badge bg-green/10 text-green border-green/20 text-xs">
          ✓ готово к использованию
        </span>
      </div>
      <div className="divide-y divide-border">
        {fields.map(({ key, label, secret }) => {
          const val = credentials[key]
          if (!val) return null
          const shown = !secret || visible[key]
          return (
            <div key={key} className="flex items-center gap-4 px-5 py-3">
              <div className="text-xs text-muted w-32 shrink-0">{label}</div>
              <div className="flex-1 font-mono text-sm text-text overflow-hidden">
                {shown
                  ? <span className="break-all">{val}</span>
                  : <span className="tracking-widest text-muted">{'•'.repeat(Math.min(val.length, 32))}</span>
                }
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {secret && (
                  <button onClick={() => toggle(key)}
                    className="text-xs text-muted hover:text-text transition-colors px-2 py-1 rounded hover:bg-white/5">
                    {visible[key] ? 'Скрыть' : 'Показать'}
                  </button>
                )}
                <button onClick={() => copy(val)}
                  className="text-xs text-muted hover:text-blue transition-colors px-2 py-1 rounded hover:bg-white/5">
                  Копировать
                </button>
              </div>
            </div>
          )
        })}
      </div>
      {/* aws cli пример */}
      <div className="px-5 py-4 border-t border-border bg-bg/50">
        <div className="text-xs text-muted mb-2 uppercase tracking-wider">Пример подключения</div>
        <pre className="text-xs font-mono text-muted whitespace-pre-wrap break-all">
{`aws --endpoint-url ${credentials.s3_endpoint || 'http://<S3_ENDPOINT>'} \
    --region us-east-1 \
    s3 ls`}
        </pre>
      </div>
    </div>
  )
}

export function ClusterDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  // Защита от невалидного id
  if (!id || id === 'undefined') {
    navigate('/clusters', { replace: true })
    return null
  }

  const [cluster, setCluster] = useState(null)
  const [jobs, setJobs]       = useState([])
  const [loading, setLoading] = useState(true)
  const [scaleOpen, setScaleOpen] = useState(false)
  const [newHost, setNewHost] = useState(emptyHost())
  const [scaling, setScaling] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError]     = useState(null)

  const fetch = useCallback(async () => {
    try {
      const [cl, jbs] = await Promise.all([
        api.clusters.get(id),
        api.clusters.jobs(id),
      ])
      setCluster(cl)
      setJobs(jbs)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  usePolling(fetch, 5000)

  function updateNewHost(field, value) {
    setNewHost(h => ({ ...h, [field]: value }))
  }

  async function handleDelete() {
    if (!confirm(`Удалить кластер ${cluster?.name}? Это запустит teardown.`)) return
    setDeleting(true)
    try {
      await api.clusters.delete(id)
      navigate('/clusters')
    } catch (e) {
      setError(e.message)
      setDeleting(false)
    }
  }

  async function handleScale(e) {
    e.preventDefault()
    setScaling(true)
    setError(null)
    try {
      // Определить groups по движку
      const groups = cluster.engine === 'seaweedfs'
        ? ['seaweedfs', 's3']
        : [cluster.engine]

      const hostPayload = {
        label:    newHost.label,
        ip:       newHost.ip,
        ssh_user: newHost.ssh_user,
        ssh_port: Number(newHost.ssh_port),
        role:     'worker',
        groups,
        zone:     newHost.zone     || undefined,
        capacity: newHost.capacity || undefined,
      }

      // Передать ключ в зависимости от режима
      hostPayload.ssh_private_key = newHost.ssh_private_key || null

      await api.clusters.scale(id, { new_hosts: [hostPayload] })
      setScaleOpen(false)
      setNewHost(emptyHost())
    } catch (e) {
      setError(e.message)
    } finally {
      setScaling(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-muted text-sm animate-pulse">
      Загрузка…
    </div>
  )

  if (!cluster) return (
    <div className="text-muted text-sm">
      Кластер не найден. <Link to="/clusters" className="text-blue hover:underline">Назад</Link>
    </div>
  )

  const canScale = cluster.status === 'ready'

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-slide-up">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <Link to="/clusters" className="text-muted hover:text-text transition-colors text-sm">
            ← Кластеры
          </Link>
          <span className="text-border">/</span>
          <h1 className="text-xl font-semibold text-text">{cluster.name}</h1>
          <EngineBadge engine={cluster.engine} />
          <StatusBadge status={cluster.status} />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setScaleOpen(v => !v)}
            disabled={!canScale}
            title={!canScale ? 'Кластер должен быть в статусе ready' : ''}
            className="btn-ghost text-sm disabled:opacity-40"
          >
            ⊕ Добавить ноду
          </button>
          <button onClick={handleDelete} disabled={deleting} className="btn-danger text-sm">
            {deleting ? 'Удаление…' : '⊗ Удалить'}
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-3 border-red/30 bg-red/5 text-red text-sm">{error}</div>
      )}

      {/* Info cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">Ноды</div>
          <div className="text-2xl font-mono font-semibold text-text">{cluster.node_count}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">S3 Endpoint</div>
          {cluster.s3_endpoint
            ? <a href={cluster.s3_endpoint} target="_blank" rel="noreferrer"
                className="text-sm font-mono text-blue hover:underline break-all">
                {cluster.s3_endpoint}
              </a>
            : <span className="text-sm text-muted">—</span>
          }
        </div>
        <div className="card p-4">
          <div className="text-xs text-muted uppercase tracking-wider mb-2">Создан</div>
          <div className="text-sm text-text">
            {new Date(cluster.created_at).toLocaleDateString('ru-RU', {
              day: '2-digit', month: 'long', year: 'numeric',
            })}
          </div>
        </div>
      </div>

      {/* Cluster ID */}
      <div className="card p-4">
        <div className="text-xs text-muted uppercase tracking-wider mb-2">Cluster ID</div>
        <div className="font-mono text-sm text-text select-all">{cluster.cluster_id}</div>
      </div>

      {/* Credentials */}
      {cluster.credentials && (
        <CredentialsCard credentials={cluster.credentials} engine={cluster.engine} />
      )}

      {/* extra_vars */}
      {cluster.extra_vars && Object.keys(cluster.extra_vars).length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-border text-xs font-medium text-muted uppercase tracking-wider">
            Extra vars
          </div>
          <pre className="p-4 text-xs font-mono text-muted overflow-x-auto">
            {JSON.stringify(cluster.extra_vars, null, 2)}
          </pre>
        </div>
      )}

      {/* Scale form */}
      {scaleOpen && (
        <form onSubmit={handleScale}
          className="card p-5 border-blue/20 bg-blue/[0.03] animate-slide-up space-y-4">
          <h3 className="text-sm font-semibold text-text">Добавить ноду</h3>

          {/* Basic fields */}
          <div className="grid grid-cols-4 gap-3">
            <div>
              <label className="label">Label</label>
              <input className="input text-xs" placeholder="node4"
                value={newHost.label}
                onChange={e => updateNewHost('label', e.target.value)} required />
            </div>
            <div>
              <label className="label">IP адрес</label>
              <input className="input text-xs" placeholder="192.168.1.111"
                value={newHost.ip}
                onChange={e => updateNewHost('ip', e.target.value)} required />
            </div>
            <div>
              <label className="label">SSH пользователь</label>
              <input className="input text-xs" placeholder="user"
                value={newHost.ssh_user}
                onChange={e => updateNewHost('ssh_user', e.target.value)} />
            </div>
            <div>
              <label className="label">SSH порт</label>
              <input className="input text-xs" type="number" placeholder="22"
                value={newHost.ssh_port}
                onChange={e => updateNewHost('ssh_port', e.target.value)} />
            </div>
          </div>

          {/* SSH key */}
          <SshKeyField host={newHost} onChange={updateNewHost} />

          {/* Garage zone/capacity */}
          {cluster.engine === 'garage' && (
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
              <div>
                <label className="label">Зона (Garage)</label>
                <input className="input text-xs" placeholder="zone1"
                  value={newHost.zone}
                  onChange={e => updateNewHost('zone', e.target.value)} />
              </div>
              <div>
                <label className="label">Ёмкость (Garage)</label>
                <input className="input text-xs" placeholder="2G"
                  value={newHost.capacity}
                  onChange={e => updateNewHost('capacity', e.target.value)} />
              </div>
            </div>
          )}

          <div className="flex gap-2 justify-end pt-2 border-t border-border">
            <button type="button" onClick={() => { setScaleOpen(false); setNewHost(emptyHost()) }}
              className="btn-ghost text-sm">
              Отмена
            </button>
            <button type="submit" disabled={scaling} className="btn-primary text-sm">
              {scaling ? 'Запуск плейбука…' : 'Добавить ноду'}
            </button>
          </div>
        </form>
      )}

      {/* Jobs */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">История задач</h2>
        </div>
        {jobs.length === 0 ? (
          <div className="py-10 text-center text-muted text-sm">Задач нет</div>
        ) : (
          <div className="divide-y divide-border">
            {jobs.map(job => (
              <div key={job.job_id}
                className="flex items-center gap-4 px-5 py-3 hover:bg-white/[0.02] transition-colors">
                <StatusBadge status={job.status} type="job" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-mono text-text">{job.playbook}</div>
                  <div className="text-xs text-muted font-mono mt-0.5">
                    {job.job_id.slice(0, 8)}…
                  </div>
                </div>
                <div className="text-xs text-muted shrink-0">
                  {new Date(job.created_at).toLocaleString('ru-RU')}
                </div>
                <Link to={`/jobs/${job.job_id}`}
                  className="text-xs text-blue hover:underline shrink-0">
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
