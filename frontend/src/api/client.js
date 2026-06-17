const BASE = 'http://localhost:8000'

async function get(path, params = {}) {
  const url = new URL(BASE + path)
  Object.entries(params).forEach(([k, v]) => v != null && url.searchParams.set(k, v))
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — POST ${path}`)
  return res.json()
}

export const api = {
  matches: (params) => get('/matches', params),
  match: (id) => get(`/matches/${id}`),
  predict: (id) => get(`/predict/${id}`),
  results: () => get('/results'),
  result: (id) => get(`/results/${id}`).catch(() => null),
  accuracy: () => get('/results/accuracy'),
  recordResult: (id, body) => post(`/results/${id}`, body),
  eloRatings: () => get('/admin/elo-ratings'),
  teamStrengths: () => get('/admin/team-strengths'),
  xgbFeatures: () => get('/admin/xgb-features'),
  modelInfo: () => get('/admin/model-info'),
  retrain: () => post('/admin/retrain'),
  tracking: () => get('/tracking'),
  trackingRefresh: () => post('/tracking/refresh'),
  trackingFreeze: () => post('/tracking/freeze'),
}
