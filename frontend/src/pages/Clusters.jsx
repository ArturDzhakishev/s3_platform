import { useState, useCallback, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { StatusBadge } from '../components/StatusBadge'
import { EngineBadge } from '../components/EngineBadge'

// ── Пустая нода ───────────────────────────────────────────────────────────
function emptyHost(role = 'worker', engine = 'seaweedfs', index = 0) {
  // Дефолтные группы по движку и роли
  const defaultGroups = {
    seaweedfs: index === 0
      ? ['seaweedfs', 's3', 'loadbalancer']
      : ['seaweedfs', 's3'],
    ceph:   [],
    garage: ['garage'],
  }
  return {
    label: '', ip: '', ssh_user: 'user', ssh_port: 22,
    ssh_private_key_path: '', ssh_private_key: '',
    role, groups: defaultGroups[engine] || [],
    zone: 'zone1', capacity: '1G',
    _keyMode: 'path',
  }
}

// ── SSH key selector ──────────────────────────────────────────────────────
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
      <div className="flex items-center gap-1 mb-1.5">
        <span className="label mb-0">SSH ключ</span>
        <div className="ml-2 flex rounded overflow-hidden border border-border text-xs">
          {[['path', 'Путь'], ['paste', 'Вставить'], ['file', 'Файл']].map(([mode, label]) => (
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
        <textarea className="input text-xs font-mono" rows={3}
          placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"}
          value={host.ssh_private_key}
          onChange={e => onChange('ssh_private_key', e.target.value)} />
      )}
      {host._keyMode === 'file' && (
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => fileRef.current?.click()}
            className="btn-ghost text-xs border border-border">
            📎 Выбрать файл ключа
          </button>
          {host.ssh_private_key
            ? <span className="text-xs text-green">✓ Загружен ({host.ssh_private_key.length} байт)</span>
            : <span className="text-xs text-muted">Файл не выбран</span>
          }
          <input ref={fileRef} type="file" className="hidden" onChange={handleFile} />
        </div>
      )}
    </div>
  )
}

// ── Группы SeaweedFS ──────────────────────────────────────────────────────
const SW_GROUPS = ['seaweedfs', 's3', 'loadbalancer']

function SeaweedGroupsField({ groups, onChange }) {
  function toggle(g) {
    const next = groups.includes(g)
      ? groups.filter(x => x !== g)
      : [...groups, g]
    // seaweedfs обязателен всегда
    if (!next.includes('seaweedfs')) next.unshift('seaweedfs')
    onChange(next)
  }

  return (
    <div>
      <label className="label">Ansible группы</label>
      <div className="flex gap-2 flex-wrap">
        {SW_GROUPS.map(g => {
          const active = groups.includes(g)
          const mandatory = g === 'seaweedfs'
          return (
            <button key={g} type="button"
              onClick={() => !mandatory && toggle(g)}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                active
                  ? 'bg-teal-500/10 text-teal-400 border-teal-500/30'
                  : 'bg-white/5 text-muted border-border hover:text-text'
              } ${mandatory ? 'cursor-default opacity-70' : 'cursor-pointer'}`}
              title={mandatory ? 'seaweedfs обязателен для всех нод' : ''}>
              [{g}]
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Одна нода ─────────────────────────────────────────────────────────────
function HostRow({ host, index, engine, onChange, onRemove, isFirst }) {
  function update(field, value) { onChange(index, field, value) }

  return (
    <div className="card p-4 border-border space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className={`badge text-xs ${isFirst
          ? 'bg-yellow/10 text-yellow border-yellow/20'
          : 'bg-white/5 text-muted border-border'}`}>
          {isFirst ? 'master' : `worker ${index}`}
        </span>
        {!isFirst && (
          <button type="button" onClick={() => onRemove(index)}
            className="ml-auto text-xs text-muted hover:text-red transition-colors px-2 py-0.5 rounded hover:bg-red/10">
            ✕ Удалить
          </button>
        )}
      </div>

      {/* IP / label / ssh */}
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
          <input className="input text-xs" value={host.ssh_user}
            onChange={e => update('ssh_user', e.target.value)} />
        </div>
        <div>
          <label className="label">SSH порт</label>
          <input className="input text-xs" type="number" value={host.ssh_port}
            onChange={e => update('ssh_port', e.target.value)} />
        </div>
      </div>

      {/* SSH key */}
      <SshKeyField host={host} onChange={(field, val) => update(field, val)} />

      {/* SeaweedFS groups */}
      {engine === 'seaweedfs' && (
        <SeaweedGroupsField
          groups={host.groups}
          onChange={val => update('groups', val)}
        />
      )}

      {/* Garage zone/capacity */}
      {engine === 'garage' && (
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border">
          <div>
            <label className="label">Зона</label>
            <input className="input text-xs" placeholder="zone1" value={host.zone}
              onChange={e => update('zone', e.target.value)} />
          </div>
          <div>
            <label className="label">Ёмкость</label>
            <input className="input text-xs" placeholder="2G" value={host.capacity}
              onChange={e => update('capacity', e.target.value)} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Форма создания кластера ───────────────────────────────────────────────
function CreateClusterForm({ onCreated, onCancel }) {
  const [name, setName]     = useState('prod-seaweedfs-01')
  const [engine, setEngine] = useState('seaweedfs')
  const [hosts, setHosts]   = useState([
    {
      label: 'node-master', ip: '192.168.1.110', ssh_user: 'user', ssh_port: 22,
      ssh_private_key_path: '/home/user/.ssh/ceph', ssh_private_key: '',
      role: 'master', groups: ['seaweedfs', 's3', 'loadbalancer'],
      zone: 'zone1', capacity: '1G', _keyMode: 'path',
    },
    {
      label: 'node-02', ip: '192.168.1.112', ssh_user: 'user', ssh_port: 22,
      ssh_private_key_path: '/home/user/.ssh/ceph', ssh_private_key: '',
      role: 'worker', groups: ['seaweedfs', 's3'],
      zone: 'zone1', capacity: '1G', _keyMode: 'path',
    },
    {
      label: 'node-03', ip: '192.168.1.113', ssh_user: 'user', ssh_port: 22,
      ssh_private_key_path: '/home/user/.ssh/ceph', ssh_private_key: '',
      role: 'worker', groups: ['seaweedfs'],
      zone: 'zone1', capacity: '1G', _keyMode: 'path',
    },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  // extra_vars по движку
  const DEFAULT_VARS = {
    seaweedfs: {
      seaweedfs_version: '3.63',
      seaweedfs_master_port: 9333,
      seaweedfs_volume_port: 8080,
      seaweedfs_filer_port: 8888,
      seaweedfs_s3_port: 8333,
      seaweedfs_volume_size_limit_mb: 30000,
    },
    ceph: {
      ceph_osd_pool_default_size: 3,
      ceph_osd_pool_default_min_size: 2,
      ceph_network: '192.168.1.0/24',
      ceph_cluster_network: '192.168.1.0/24',
      ceph_rgw_enable: true,
    },
    garage: {
      garage_version: '2.2.0',
      garage_rpc_port: 3901,
      garage_replication_factor: 1,
      name_bucket: 'test',
    },
  }
  const [extraVars, setExtraVars] = useState(
    JSON.stringify(DEFAULT_VARS.seaweedfs, null, 2)
  )

  function handleEngineChange(e) {
    const eng = e.target.value
    setEngine(eng)
    setExtraVars(JSON.stringify(DEFAULT_VARS[eng] || {}, null, 2))
    // Сбросить hosts с правильными дефолтными группами
    setHosts(h => h.map((host, i) => ({
      ...host,
      groups: emptyHost(i === 0 ? 'master' : 'worker', eng, i).groups,
    })))
  }

  function updateHost(i, field, value) {
    setHosts(h => h.map((x, idx) => idx === i ? { ...x, [field]: value } : x))
  }

  function addHost() {
    setHosts(h => [...h, emptyHost('worker', engine, h.length)])
  }

  function removeHost(i) {
    if (hosts.length <= 1) return
    setHosts(h => h.filter((_, idx) => idx !== i))
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
            groups:   h.groups,
            zone:     h.zone || undefined,
            capacity: h.capacity || undefined,
          }
          if (h._keyMode === 'path') {
            host.ssh_private_key_path = h.ssh_private_key_path || null
          } else {
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
            placeholder="prod-seaweedfs-01" required />
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
            <span className="ml-2 text-xs text-muted">
              {hosts.length} шт. · первая нода всегда master
            </span>
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
        <textarea className="input font-mono text-xs" rows={7}
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
            Кластер создаётся… job{' '}
            <span className="font-mono text-xs text-blue">{created.job_id.slice(0, 8)}…</span>
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
