import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { flag } from '../utils/flags.js'
import { pct, formatDate, impliedOdds } from '../utils/format.js'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'

const OUTCOMES = [
  { key: 'home', label: '1', desc: 'Victorie acasă' },
  { key: 'draw', label: 'X', desc: 'Egal' },
  { key: 'away', label: '2', desc: 'Victorie deplasare' },
]

function getProbForOutcome(pred, outcome) {
  if (!pred) return 0
  if (outcome === 'home') return pred.prob_home
  if (outcome === 'draw') return pred.prob_draw
  if (outcome === 'away') return pred.prob_away
  return 0
}

function SlipMatch({ match, pred, outcome, onChangeOutcome, onRemove }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-xs text-gray-400 mb-1">
            {formatDate(match.date)} · Grupa {match.group ?? ''} · {match.city}
          </div>
          <div className="font-semibold text-white text-sm">
            {flag(match.home_team)} {match.home_team} vs {match.away_team} {flag(match.away_team)}
          </div>
        </div>
        <button onClick={onRemove} className="text-gray-600 hover:text-red-400 text-lg leading-none ml-2">×</button>
      </div>

      {/* Outcome selector */}
      <div className="flex gap-2">
        {OUTCOMES.map(({ key, label, desc }) => {
          const prob = getProbForOutcome(pred, key)
          const selected = outcome === key
          return (
            <button
              key={key}
              onClick={() => onChangeOutcome(key)}
              className={`flex-1 rounded-lg p-2 text-center transition-all border ${
                selected
                  ? 'bg-cyan-500/20 border-cyan-500 text-cyan-400'
                  : 'bg-navy-900 border-navy-700 text-gray-400 hover:border-gray-500'
              }`}
            >
              <div className="font-bold text-lg">{label}</div>
              <div className="text-xs mt-0.5">{prob > 0 ? pct(prob) : '—'}</div>
              {prob > 0 && (
                <div className="text-xs text-gray-500">@{impliedOdds(prob)}</div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function MatchPickerRow({ match, onAdd, isAdded }) {
  const { data: pred } = useQuery({
    queryKey: ['predict', match.match_id],
    queryFn: () => api.predict(match.match_id),
    enabled: match.home_team !== 'TBD',
    staleTime: 60_000,
  })

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-navy-700 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-white truncate">
          {flag(match.home_team)} {match.home_team} vs {match.away_team} {flag(match.away_team)}
        </div>
        <div className="text-xs text-gray-500">
          {formatDate(match.date)} · {match.group ? `Gr. ${match.group}` : match.stage}
        </div>
      </div>
      {pred && (
        <div className="text-xs text-gray-400 hidden md:block">
          <span className="text-cyan-400">{pct(pred.prob_home)}</span>
          {' / '}
          <span>{pct(pred.prob_draw)}</span>
          {' / '}
          <span className="text-amber-400">{pct(pred.prob_away)}</span>
        </div>
      )}
      <button
        onClick={() => onAdd(match)}
        disabled={isAdded}
        className={`text-xs px-3 py-1 rounded-lg font-medium transition-colors ${
          isAdded
            ? 'bg-navy-700 text-gray-500 cursor-not-allowed'
            : 'bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30'
        }`}
      >
        {isAdded ? '✓' : '+ Adaugă'}
      </button>
    </div>
  )
}

export default function BettingSlip() {
  const [slip, setSlip] = useState([]) // [{matchId, outcome}]
  const [showPicker, setShowPicker] = useState(false)

  const { data: matchesData, isLoading, error } = useQuery({
    queryKey: ['matches', 'scheduled-slip'],
    queryFn: () => api.matches({ status: 'scheduled', limit: 30 }),
    enabled: showPicker,
  })

  // Fetch predictions for all slip items
  const slipMatches = slip.map(s => s.matchId)
  const predQueries = useQuery({
    queryKey: ['predict-batch', slipMatches.join(',')],
    queryFn: async () => {
      const results = {}
      await Promise.all(
        slipMatches.map(async (id) => {
          try {
            results[id] = await api.predict(id)
          } catch {}
        })
      )
      return results
    },
    enabled: slipMatches.length > 0,
    staleTime: 60_000,
  })

  const { data: matchInfoMap } = useQuery({
    queryKey: ['matches-info', slipMatches.join(',')],
    queryFn: async () => {
      const results = {}
      await Promise.all(
        slipMatches.map(async (id) => {
          try {
            results[id] = await api.match(id)
          } catch {}
        })
      )
      return results
    },
    enabled: slipMatches.length > 0,
  })

  const predictions = predQueries.data ?? {}
  const matchInfo = matchInfoMap ?? {}

  // Combined probability
  const combinedProb = slip.reduce((acc, { matchId, outcome }) => {
    const prob = getProbForOutcome(predictions[matchId], outcome)
    return prob > 0 ? acc * prob : acc
  }, 1)

  function addToSlip(match) {
    if (slip.find(s => s.matchId === match.match_id)) return
    setSlip(prev => [...prev, { matchId: match.match_id, outcome: 'home' }])
    setShowPicker(false)
  }

  function removeFromSlip(matchId) {
    setSlip(prev => prev.filter(s => s.matchId !== matchId))
  }

  function changeOutcome(matchId, outcome) {
    setSlip(prev => prev.map(s => s.matchId === matchId ? { ...s, outcome } : s))
  }

  function copySlip() {
    const lines = slip.map(({ matchId, outcome }) => {
      const m = matchInfo[matchId]
      const pred = predictions[matchId]
      const prob = getProbForOutcome(pred, outcome)
      if (!m) return `${matchId}: ${outcome}`
      const outLabel = { home: '1', draw: 'X', away: '2' }[outcome]
      return `${m.home_team} vs ${m.away_team}: ${outLabel} (${pct(prob)})`
    })
    const text = [
      'WC 2026 Predictor — Bilet',
      '—'.repeat(30),
      ...lines,
      '—'.repeat(30),
      `Probabilitate combinată: ${pct(combinedProb)}`,
      'Proiect educațional · Nu este un instrument de pariuri',
    ].join('\n')
    navigator.clipboard.writeText(text).catch(() => {})
  }

  const scheduledMatches = matchesData?.matches?.filter(
    m => m.home_team !== 'TBD' && m.away_team !== 'TBD'
  ) ?? []

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Bilet Predicții</h1>
        <div className="text-xs text-gray-500">educațional · nu pariuri</div>
      </div>

      {/* Slip items */}
      {slip.length === 0 ? (
        <div className="card p-8 text-center text-gray-400 mb-4">
          <div className="text-4xl mb-3">🎫</div>
          <div className="font-medium">Biletul este gol</div>
          <div className="text-sm mt-1">Adaugă meciuri din lista de mai jos</div>
        </div>
      ) : (
        <div className="space-y-3 mb-4">
          {slip.map(({ matchId, outcome }) => {
            const match = matchInfo[matchId]
            const pred = predictions[matchId]
            if (!match) return <div key={matchId} className="card p-4 text-gray-500 text-sm">Se încarcă...</div>
            return (
              <SlipMatch
                key={matchId}
                match={match}
                pred={pred}
                outcome={outcome}
                onChangeOutcome={(o) => changeOutcome(matchId, o)}
                onRemove={() => removeFromSlip(matchId)}
              />
            )
          })}
        </div>
      )}

      {/* Summary */}
      {slip.length > 0 && (
        <div className="card p-4 mb-4 border-amber-500/30">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400 mb-1">{slip.length} selecții · Probabilitate combinată</div>
              <div className="text-3xl font-bold text-amber-400">{pct(combinedProb)}</div>
              <div className="text-xs text-gray-500 mt-1">cotă implicată {impliedOdds(combinedProb)}</div>
            </div>
            <button onClick={copySlip} className="btn-secondary">
              📋 Copiază biletul
            </button>
          </div>
        </div>
      )}

      {/* Add matches */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-300">Adaugă Meciuri</h3>
          <button
            onClick={() => setShowPicker(!showPicker)}
            className="text-xs text-cyan-400 hover:underline"
          >
            {showPicker ? '▲ Ascunde' : '▼ Arată meciuri'}
          </button>
        </div>

        {showPicker && (
          isLoading ? <LoadingSpinner size="sm" /> :
          error ? <ErrorMsg message={error.message} /> :
          scheduledMatches.length === 0 ? (
            <div className="text-sm text-gray-500 text-center py-4">Niciun meci programat disponibil.</div>
          ) : (
            <div>
              {scheduledMatches.map(m => (
                <MatchPickerRow
                  key={m.match_id}
                  match={m}
                  onAdd={addToSlip}
                  isAdded={slip.some(s => s.matchId === m.match_id)}
                />
              ))}
            </div>
          )
        )}
      </div>

      <p className="text-xs text-gray-600 text-center mt-6 pb-2">
        ⚠️ Proiect educațional de statistică · Probabilitățile sunt estimate · Nu pariați bani reali bazat pe aceste predicții
      </p>
    </div>
  )
}
