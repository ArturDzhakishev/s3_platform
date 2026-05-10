const BASE = '/api/v1'

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(err?.detail?.message || err?.message || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Clusters ──────────────────────────────────────────────────────────────
export const api = {
  clusters: {
    list:   (params = {}) => {
      const q = new URLSearchParams(params).toString()
      return request('GET', `/clusters${q ? '?' + q : ''}`)
    },
    get:    (id)      => request('GET',    `/clusters/${id}`),
    create: (body)    => request('POST',   '/clusters', body),
    delete: (id)      => request('DELETE', `/clusters/${id}`),
    scale:  (id, body)=> request('POST',   `/clusters/${id}/scale`, body),
    jobs:   (id)      => request('GET',    `/clusters/${id}/jobs`),
  },

  // ── Jobs ────────────────────────────────────────────────────────────────
  jobs: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString()
      return request('GET', `/jobs${q ? '?' + q : ''}`)
    },
    get:  (id) => request('GET', `/jobs/${id}`),
  },

  // ── Hosts ───────────────────────────────────────────────────────────────
  hosts: {
    list: () => request('GET', '/hosts'),
    get:  (id) => request('GET', `/hosts/${id}`),
    ping: (body) => request('POST', '/ping', body),
  },
}
