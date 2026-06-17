import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client.js'
import { flag } from '../utils/flags.js'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'

/* ── Feature bar ──────────────────────────────── */
function FeatureBar({ name, importance, max }) {
  const pct = max > 0 ? (importance / max) * 100 : 0
  const isElo = name.startsWith('elo')
  const isDC = name.startsWith('dc')
  const isForm = name.startsWith('fh') || name.startsWith('fa')
  const isH2H = name.startsWith('h2h')
  const color = isElo ? '#22D3EE' : isDC ? '#A78BFA' : isForm ? '#F5C518' : isH2H ? '#F97316' : '#9CA3AF'

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-36 text-xs text-gray-300 font-mono truncate flex-shrink-0">{name}</div>
      <div className="flex-1 bg-navy-900 rounded-full h-2 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
             style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <div className="w-12 text-right text-xs text-gray-400 font-mono">{(importance * 100).toFixed(1)}%</div>
    </div>
  )
}

/* ── Elo rankings ──────────────────────────────── */
function EloTable({ data }) {
  const [search, setSearch] = useState('')
  const filtered = (data ?? []).filter(r =>
    r.team.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Caută echipă..."
        className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 mb-3 focus:outline-none focus:border-cyan-500"
      />
      <div className="space-y-1 max-h-[500px] overflow-y-auto pr-1">
        {filtered.map((r, i) => {
          const pct = ((r.elo - 1200) / 600) * 100  // scale 1200-1800
          return (
            <div key={r.team} className="flex items-center gap-3 py-1.5">
              <div className="w-6 text-xs text-gray-500 text-right flex-shrink-0">{i + 1}</div>
              <div className="w-6 flex-shrink-0 text-base">{flag(r.team)}</div>
              <div className="flex-1 text-sm text-gray-200 min-w-0 truncate">{r.team}</div>
              <div className="w-24 bg-navy-900 rounded-full h-1.5 overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full"
                     style={{ width: `${Math.min(Math.max(pct, 5), 100)}%` }} />
              </div>
              <div className="w-14 text-right text-sm font-bold text-cyan-400">{Math.round(r.elo)}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ── DC Strengths ──────────────────────────────── */
function DCTable({ data }) {
  const [search, setSearch] = useState('')
  const sorted = [...(data ?? [])].sort((a, b) => b.overall - a.overall)
  const filtered = sorted.filter(r =>
    r.team.toLowerCase().includes(search.toLowerCase())
  )
  const maxAtt = Math.max(...(data ?? []).map(r => r.attack), 1)
  const maxDef = Math.max(...(data ?? []).map(r => r.defense), 1)

  return (
    <div>
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Caută echipă..."
        className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 mb-3 focus:outline-none focus:border-cyan-500"
      />
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-gray-500 uppercase">
            <tr>
              <th className="pb-2 text-left">#</th>
              <th className="pb-2 text-left">Echipă</th>
              <th className="pb-2 text-right">Atac</th>
              <th className="pb-2 text-right">Apărare</th>
              <th className="pb-2 text-right">Overall</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-navy-700">
            {filtered.slice(0, 30).map((r, i) => (
              <tr key={r.team} className="hover:bg-navy-900/50">
                <td className="py-1.5 text-gray-500 w-6">{i + 1}</td>
                <td className="py-1.5">
                  <div className="flex items-center gap-1.5">
                    <span>{flag(r.team)}</span>
                    <span className="text-gray-200">{r.team}</span>
                  </div>
                </td>
                <td className="py-1.5 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <div className="w-16 bg-navy-700 rounded-full h-1 overflow-hidden">
                      <div className="h-full bg-green-400 rounded-full"
                           style={{ width: `${(r.attack / maxAtt) * 100}%` }} />
                    </div>
                    <span className="text-green-400 w-8">{r.attack.toFixed(2)}</span>
                  </div>
                </td>
                <td className="py-1.5 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <div className="w-16 bg-navy-700 rounded-full h-1 overflow-hidden">
                      <div className="h-full bg-red-400 rounded-full"
                           style={{ width: `${(r.defense / maxDef) * 100}%` }} />
                    </div>
                    <span className="text-red-400 w-8">{r.defense.toFixed(2)}</span>
                  </div>
                </td>
                <td className="py-1.5 text-right font-bold text-cyan-400">{r.overall.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ── Retrain button ────────────────────────────── */
function RetrainPanel() {
  const qc = useQueryClient()
  const [log, setLog] = useState(null)

  const mut = useMutation({
    mutationFn: api.retrain,
    onSuccess: (data) => {
      setLog(data)
      qc.invalidateQueries()
    },
    onError: (err) => setLog({ status: 'error', message: err.message }),
  })

  return (
    <div className="card p-5 border-amber-500/20">
      <h3 className="text-sm font-semibold text-amber-400 mb-1">Reantrenare Model</h3>
      <p className="text-xs text-gray-400 mb-4">
        Reantrenează modelul pe toate rezultatele WC 2026 înregistrate.
        Durată estimată: 2–3 minute.
      </p>
      <button
        onClick={() => mut.mutate()}
        disabled={mut.isPending}
        className={`btn-primary w-full ${mut.isPending ? 'opacity-60 cursor-wait' : ''}`}
      >
        {mut.isPending ? '⏳ Antrenare în curs (~2 min)...' : '🔄 Reantrenează Modelul'}
      </button>
      {log && (
        <div className={`mt-3 p-3 rounded-lg text-xs ${
          log.status === 'ok' ? 'bg-green-500/10 text-green-400' :
          log.status === 'skipped' ? 'bg-amber-500/10 text-amber-400' :
          'bg-red-500/10 text-red-400'
        }`}>
          {log.status === 'ok' && (
            <div className="space-y-0.5">
              <div>✓ Model: <strong>{log.model}</strong></div>
              <div>✓ Antrenat pe: <strong>{log.trained_on}</strong> rezultate WC</div>
              <div>✓ Acuratețe curentă: <strong>
                {log.accuracy?.with_prediction > 0
                  ? `${Math.round((log.accuracy.correct / log.accuracy.with_prediction) * 100)}%`
                  : 'N/A'}
              </strong></div>
              <div>✓ XGB: <strong>{log.xgb_fitted ? 'activ' : 'inactiv'}</strong></div>
            </div>
          )}
          {log.status !== 'ok' && <div>{log.message}</div>}
        </div>
      )}
    </div>
  )
}

/* ── Main page ─────────────────────────────────── */
const TABS = [
  { id: 'xgb', label: 'XGBoost Features' },
  { id: 'elo', label: 'Elo Rankings' },
  { id: 'dc', label: 'DC Strengths' },
  { id: 'retrain', label: 'Reantrenare' },
]

export default function ModelIntel() {
  const [tab, setTab] = useState('xgb')

  const { data: modelInfo } = useQuery({ queryKey: ['model-info'], queryFn: api.modelInfo })
  const { data: xgbFeat, isLoading: xLoading, error: xErr } = useQuery({
    queryKey: ['xgb-features'], queryFn: api.xgbFeatures, enabled: tab === 'xgb',
  })
  const { data: eloData, isLoading: eLoading } = useQuery({
    queryKey: ['elo-ratings'], queryFn: api.eloRatings, enabled: tab === 'elo',
  })
  const { data: dcData, isLoading: dLoading } = useQuery({
    queryKey: ['team-strengths'], queryFn: api.teamStrengths, enabled: tab === 'dc',
  })

  const maxImportance = xgbFeat ? Math.max(...xgbFeat.map(f => f.importance)) : 1

  const groupLegend = [
    { color: '#22D3EE', label: 'Elo' },
    { color: '#A78BFA', label: 'Dixon-Coles' },
    { color: '#F5C518', label: 'Formă recentă' },
    { color: '#F97316', label: 'Head-to-Head' },
  ]

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Inteligența Modelului</h1>
          <p className="text-sm text-gray-400 mt-1">
            {modelInfo ? modelInfo.ensemble : 'Model probabilistic WC 2026'}
          </p>
        </div>
        {modelInfo && (
          <div className="card px-4 py-2 text-xs text-right">
            <div className="text-cyan-400 font-bold">{modelInfo.ensemble}</div>
            <div className="text-gray-400 mt-0.5">
              {[
                modelInfo.weights.dixon_coles > 0 && `DC ${Math.round(modelInfo.weights.dixon_coles * 100)}%`,
                modelInfo.weights.elo > 0 && `Elo ${Math.round(modelInfo.weights.elo * 100)}%`,
                modelInfo.weights.xgboost > 0 && `XGB ${Math.round(modelInfo.weights.xgboost * 100)}%`,
              ].filter(Boolean).join(' · ')}
            </div>
            {modelInfo.calibrated && (
              <div className="text-purple-400 mt-0.5">✓ {modelInfo.calibration} calibrat</div>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 card p-1">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.id
                ? 'bg-cyan-500/20 text-cyan-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* XGB Features */}
      {tab === 'xgb' && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-200">Feature Importance XGBoost</h2>
            <div className="flex gap-3">
              {groupLegend.map(g => (
                <div key={g.label} className="flex items-center gap-1 text-xs text-gray-400">
                  <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: g.color }} />
                  {g.label}
                </div>
              ))}
            </div>
          </div>
          {xLoading ? <LoadingSpinner /> :
           xErr ? <ErrorMsg message={xErr.message} /> :
           (xgbFeat ?? []).map(f => (
             <FeatureBar key={f.feature} name={f.feature} importance={f.importance} max={maxImportance} />
           ))}
          <p className="text-xs text-gray-600 mt-4">
            26 features · Antrenat pe ~{'>'}50,000 meciuri internaționale istorice
          </p>
        </div>
      )}

      {/* Elo */}
      {tab === 'elo' && (
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">Clasament Elo Global</h2>
          {eLoading ? <LoadingSpinner /> : <EloTable data={eloData} />}
        </div>
      )}

      {/* DC */}
      {tab === 'dc' && (
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">Putere Echipe — Dixon-Coles</h2>
          {dLoading ? <LoadingSpinner /> : <DCTable data={dcData} />}
        </div>
      )}

      {/* Retrain */}
      {tab === 'retrain' && <RetrainPanel />}
    </div>
  )
}
