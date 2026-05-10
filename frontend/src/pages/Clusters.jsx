import { useState, useCallback, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'
import { EngineBadge } from '../components/EngineBadge'

// ── Пустая нода ───────────────────────────────────────────────────────────
function emptyHost(role = 'worker') {
  return {
    label: '', ip: '', ssh_user: 'user', ssh_port: 22,
    ssh_private_key_path: '', ssh_private_key: '',
    role, groups: [], zone: 'zone1', capacity: '1G',
    _keyMode: 'path', // 'path' | 'paste' | 'file'
  }
}

// ── Компонент одной ноды ──────────────────────────────────────────────────
function HostRow({ host, index, engine, onChange, onRemove, isFirst }) {
  const fileRef = useRef(null)

  function update(field, value) {
    onChange(index, field, value)
  }

  function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => update('ssh_private_key', ev.target.result)
    reader.readAsText(file)
    update('_keyMode', 'file')
  }

  return (
    <div className="card p-4 border-border space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className={`badge text-xs ${isFirst ? 'bg-yellow/10 text-yellow border-yellow/20' : 'bg-white/5 text-muted border-border'}`}>
          {isFirst ? 'master' : `worker ${index}`}
        </span>
        {!isFirst && (
          <button type="button" onClick={() => onRemove(index)}
            className="ml-auto text-xs text-muted hover:text-red transition-colors px-2 py-0.5 rounded hover:bg-red/10">
            ✕ Удалить
          </button>
        )}
      </div>

      {/* Main fields */}
      <div className="grid grid-cols-4 gap-2">
        <div>
          <label className="label">Label</label>
          <input className="input text-xs" placeholder="node1" value={host.label}
            onChange={e => update('label', e.target.value)} required />
        </div>
        <div>
          <label className="label">IP адрес</label>
          <input className="input text-xs" placeholder="192.168.1.110" value={host.ip}
            onChange={e => update('ip', e.target.value)} required />
        </div>
        <div>
          <label className="label">SSH пользователь</label>
          <input className="input text-xs" placeholder="user" value={host.ssh_user}
            onChange={e => update('ssh_user', e.target.value)} />
        </div>
        <div>
          <label className="label">SSH порт</label>
          <input className="input text-xs" type="number" placeholder="22" value={host.ssh_port}
            onChange={e => update('ssh_port', e.target.value)} />
        </div>
      </div>

      {/* SSH key */}
      <div>
        <div className="flex items-center gap-1 mb-2">
          <span className="label mb-0">SSH ключ</span>
          <div className="ml-2 flex rounded overflow-hidden border border-border text-xs">
            {[['path', 'Путь'], ['paste', 'Вставить'], ['file', 'Файл']].map(([mode, label]) => (
              <button key={mode} type="button"
                onClick={() => update('_keyMode', mode)}
                className={`px-2.5 py-1 transition-colors ${host._keyMode === mode ? 'bg-blue/20 text-blue' : 'text-muted hover:text-text hover:bg-white/5'}`}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {host._keyMode === 'path' && (
          <input className="input text-xs font-mono" placeholder="/home/user/.ssh/id_rsa"
            value={host.ssh_private_key_path}
            onChange={e => update('ssh_private_key_path', e.target.value)} />
        )}

        {host._keyMode === 'paste' && (
          <textarea className="input text-xs font-mono" rows={4}
            placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----"
            value={host.ssh_private_key}
            onChange={e => update('ssh_private_key', e.target.value)} />
        )}

        {host._keyMode === 'file' && (
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => fileRef.current?.click()}
              className="btn-ghost text-xs border border-border">
              📎 Выбрать файл ключа
            </button>
            {host.ssh_private_key && (
              <span className="text-xs text-green">✓ Ключ загружен ({host.ssh_private_key.length} байт)</span>
            )}
            <input ref={fileRef} type="file" className="hidden"
              accept="*" onChange={handleFile} />
          </div>
        )}
      </div>

      {/* Garage-specific */}
      {engine === 'garage' && (
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border">
          <div>
            <label className="label">Зона (Garage)</label>
            <input className="input text-xs" placeholder="zone1" value={host.zone}
              onChange={e => update('zone', e.target.value)} />
          </div>
          <div>
            <label className="label">Ёмкость (Garage)</label>
            <input className="input text-xs" placeholder="2G" value={host.capacity}
              onChange={e => update('capacity', e.target.value)} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Форма создания ─────────────────────────────────────────────────────────
function CreateClusterForm({ onCreated, onCancel }) {
  const [name, setName]       = useState('')
  const [engine, setEngine]   = useState('seaweedfs')
  const [hosts, setHosts]     = useState([emptyHost('master'), emptyHost(), emptyHost()])
  const [extraVars, setExtraVars] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const defaultVars = {
    seaweedfs: { seaweedfs_version: '3.63', seaweedfs_master_port: 9333, seaweedfs_volume_port: 8080, seaweedfs_filer_port: 8888, seaweedfs_s3_port: 8333 },
    ceph:      { ceph_osd_pool_default_size: 3, ceph_osd_pool_default_min_size: 2, ceph_network: '192.168.1.0/24', ceph_rgw_enable: true },
    garage:    { garage_version: '2.2.0', garage_rpc_port: 3901, garage_replication_factor: 1, name_bucket: 'test' },
  }

  function handleEngineChange(e) {
    const eng = e.target.value
    setEngine(eng)
    setExtraVars(JSON.stringify(defaultVars[eng] || {}, null, 2))
  }

  // Инициализировать extra_vars при первом рендере
  useState(() => {
    setExtraVars(JSON.stringify(defaultVars[engine], null, 2))
  })

  function updateHost(i, field, value) {
    setHosts(h => h.map((x, idx) => idx === i ? { ...x, [field]: value } : x))
  }

  function addHost() {
    setHosts(h => [...h, emptyHost()])
  }

  function removeHost(i) {
    if (hosts.length <= 1) return
    setHosts(h => h.filter((_, idx) => idx !== i))
  }

  // Автоматически назначить groups по движку
  function buildGroups(engine, index) {
    if (engine === 'seaweedfs') {
      return index === 0
        ? ['seaweedfs', 's3', 'loadbalancer']
        : ['seaweedfs', 's3']
    }
    return [engine]
  }

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      let extra = {}
      try { extra = JSON.parse(extraVars || '{}') }
      catch { throw new Error('extra_vars: невалидный JSON') }

      const payload = {
        name,
        engine,
        hosts: hosts.map((h, i) => {
          const host = {
            label:    h.label,
            ip:       h.ip,
            ssh_user: h.ssh_user,
            ssh_port: Number(h.ssh_port),
            role:     i === 0 ? 'master' : 'worker',
            groups:   buildGroups(engine, i),
            zone:     h.zone,
            capacity: h.capacity,
          }
          // Передать ключ в зависимости от режима
          if (h._keyMode === 'path') {
            host.ssh_private_key_path = h.ssh_private_key_path || null
          } else {
            // paste или file — передать содержимое ключа
            host.ssh_private_key = h.ssh_private_key || null
          }
          return host
        }),
        extra_vars: extra,
      }

      const res = await api.clusters.create(payload)
      onCreated(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {error && (
        <div className="card p-3 border-red/30 bg-red/5 text-red text-sm">{error}</div>
      )}

      {/* Name + Engine */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Имя кластера</label>
          <input className="input" value={name} onChange={e => setName(e.target.value)}
            placeholder="prod-ceph-01" required />
        </div>
        <div>
          <label className="label">Движок</label>
          <select className="input" value={engine} onChange={handleEngineChange}>
            <option value="seaweedfs">SeaweedFS</option>
            <option value="ceph">Ceph</option>
            <option value="garage">Garage</option>
          </select>
        </div>
      </div>

      {/* Hosts */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="label mb-0">Ноды</span>
            <span className="ml-2 text-xs text-muted">{hosts.length} шт. · первая нода всегда master</span>
          </div>
          <button type="button" onClick={addHost} className="btn-primary text-xs py-1.5 px-3">
            + Добавить ноду
          </button>
        </div>
        <div className="space-y-3">
          {hosts.map((h, i) => (
            <HostRow
              key={i}
              host={h}
              index={i}
              engine={engine}
              onChange={updateHost}
              onRemove={removeHost}
              isFirst={i === 0}
            />
          ))}
        </div>
      </div>

      {/* extra_vars */}
      <div>
        <label className="label">extra_vars (JSON)</label>
        <textarea className="input font-mono text-xs" rows={6}
          value={extraVars} onChange={e => setExtraVars(e.target.value)} />
      </div>

      <div className="flex gap-3 justify-end pt-2 border-t border-border">
        <button type="button" onClick={onCancel} className="btn-ghost">Отмена</button>
        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? 'Создание…' : `Создать кластер (${hosts.length} нод)`}
        </button>
      </div>
    </form>
  )
}

// ── Основная страница ──────────────────────────────────────────────────────
export function Clusters() {
  const [clusters, setClusters] = useState([])
  const [loading, setLoading]   = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [created, setCreated]   = useState(null)
  const navigate = useNavigate()

  const fetchClusters = useCallback(async () => {
    try {
      const list = await api.clusters.list()
      setClusters(list)
      // Если только что создали — ищем cluster_id через job
      if (created) {
        try {
          const job = await api.jobs.get(created.job_id)
          if (job?.cluster_id) {
            setCreated(null)
            navigate(`/clusters/${job.cluster_id}`)
          }
        } catch (_) {}
      }
    } finally {
      setLoading(false)
    }
  }, [created, navigate])

  usePolling(fetchClusters, 3000)

  function handleCreated(res) {
    setShowForm(false)
    if (res?.cluster_id) {
      navigate(`/clusters/${res.cluster_id}`)
      return
    }
    if (res?.job_id) {
      setCreated({ job_id: res.job_id })
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Кластеры</h1>
          <p className="text-sm text-muted mt-1">{clusters.length} кластеров</p>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="btn-primary">
          {showForm ? '✕ Закрыть' : '+ Новый кластер'}
        </button>
      </div>

      {created && (
        <div className="card p-4 border-blue/20 bg-blue/5 flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-blue animate-pulse flex-shrink-0" />
          <span className="text-sm text-muted">
            Кластер создаётся… job <span className="font-mono text-xs text-blue">{created.job_id.slice(0,8)}…</span>
          </span>
          <Link to={`/jobs/${created.job_id}`} className="ml-auto text-xs text-blue hover:underline">
            Смотреть лог →
          </Link>
        </div>
      )}

      {showForm && (
        <div className="card p-6 border-blue/20 bg-blue/[0.03] animate-slide-up">
          <h2 className="text-sm font-semibold text-text mb-5">Новый кластер</h2>
          <CreateClusterForm onCreated={handleCreated} onCancel={() => setShowForm(false)} />
        </div>
      )}

      {loading ? (
        <div className="text-center py-16 text-muted text-sm animate-pulse">Загрузка…</div>
      ) : clusters.length === 0 && !showForm ? (
        <div className="card py-16 text-center">
          <div className="text-muted text-sm mb-3">Кластеров нет</div>
          <button onClick={() => setShowForm(true)} className="btn-primary text-sm">
            + Создать первый кластер
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {clusters.map(c => (
            <Link key={c.cluster_id} to={`/clusters/${c.cluster_id}`}
              className="card p-4 flex items-center gap-4 hover:border-blue/30 hover:bg-blue/[0.02] transition-all block">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-sm font-medium text-text">{c.name}</span>
                  <EngineBadge engine={c.engine} />
                  <StatusBadge status={c.status} />
                </div>
                <div className="text-xs text-muted font-mono mt-1">{c.cluster_id}</div>
              </div>
              <div className="text-right shrink-0 space-y-1">
                <div className="text-sm font-mono text-muted">{c.node_count} нод</div>
                {c.s3_endpoint && (
                  <div className="text-xs text-blue font-mono">{c.s3_endpoint}</div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
