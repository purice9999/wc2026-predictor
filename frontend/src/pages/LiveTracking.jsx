import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { flag } from '../utils/flags'
import { pct, formatDate, stageLabel } from '../utils/format'

// ─── Metric card ──────────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, highlight, warn }) {
  return (
    <div className={`rounded-xl p-4 border ${warn ? 'border-yellow-500/30 bg-yellow-500/5' : 'border-navy-700 bg-navy-800'}`}>
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? 'text-cyan-400' : 'text-white'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  )
}

// ─── Outcome badge ────────────────────────────────────────────────────────────
function OutcomeBadge({ winner }) {
  const map = { home: '1', draw: 'X', away: '2' }
  const colors = {
    home: 'bg-cyan-500/20 text-cyan-300',
    draw: 'bg-yellow-500/20 text-yellow-300',
    away: 'bg-purple-500/20 text-purple-300',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${colors[winner] ?? 'bg-gray-700 text-gray-300'}`}>
      {map[winner] ?? '?'}
    </span>
  )
}

// ─── Probability mini-bar ─────────────────────────────────────────────────────
function MiniProbs({ ph, pd, pa, winner }) {
  const bars = [
    { label: '1', p: ph, key: 'home', color: 'bg-cyan-500' },
    { label: 'X', p: pd, key: 'draw', color: 'bg-yellow-400' },
    { label: '2', p: pa, key: 'away', color: 'bg-purple-500' },
  ]
  return (
    <div className="flex gap-1 items-end h-8">
      {bars.map(({ label, p, key, color }) => (
        <div key={key} className="flex flex-col items-center gap-0.5">
          <span className={`text-[10px] font-medium ${winner === key ? 'text-white' : 'text-gray-500'}`}>
            {pct(p)}
          </span>
          <div className="w-5 bg-navy-700 rounded-sm overflow-hidden" style={{ height: `${Math.max(p * 24, 3)}px` }}>
            <div className={`w-full h-full ${color} ${winner === key ? '' : 'opacity-40'}`} />
          </div>
          <span className={`text-[9px] ${winner === key ? 'text-gray-300' : 'text-gray-600'}`}>{label}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Completed match row ──────────────────────────────────────────────────────
function CompletedRow({ match }) {
  const { home_team, away_team, date, stage, group, frozen, result, correct, btts_correct, over_2_5_correct } = match
  const { home_score, away_score } = result

  return (
    <div className={`rounded-xl border p-3 sm:p-4 ${correct ? 'border-green-500/25 bg-green-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{formatDate(date)}</span>
          <span>·</span>
          <span>{group ? `Gr. ${group}` : stageLabel(stage)}</span>
        </div>
        <span className={`text-lg font-bold ${correct ? 'text-green-400' : 'text-red-400'}`}>
          {correct ? '✓' : '✗'}
        </span>
      </div>

      {/* Teams + scores */}
      <div className="flex items-center gap-3 mb-3">
        {/* Home team */}
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-xl">{flag(home_team)}</span>
          <span className="text-sm font-medium text-white truncate">{home_team}</span>
        </div>

        {/* Score boxes */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Predicted */}
          <div className="text-center">
            <p className="text-[10px] text-gray-500 mb-0.5">Predicție</p>
            <div className="bg-navy-700 rounded px-2 py-0.5 text-sm font-mono text-gray-300">
              {frozen?.most_likely_score
                ? `${frozen.most_likely_score.home}–${frozen.most_likely_score.away}`
                : '–'}
            </div>
          </div>
          <span className="text-gray-600 text-xs">vs</span>
          {/* Actual */}
          <div className="text-center">
            <p className="text-[10px] text-gray-500 mb-0.5">Real</p>
            <div className={`rounded px-2 py-0.5 text-sm font-mono font-bold ${correct ? 'bg-green-500/20 text-green-300' : 'bg-red-500/15 text-red-300'}`}>
              {home_score}–{away_score}
            </div>
          </div>
        </div>

        {/* Away team */}
        <div className="flex items-center gap-1.5 flex-1 min-w-0 justify-end">
          <span className="text-sm font-medium text-white truncate text-right">{away_team}</span>
          <span className="text-xl">{flag(away_team)}</span>
        </div>
      </div>

      {/* Probs + markets */}
      {frozen && (
        <div className="flex items-end justify-between border-t border-navy-700 pt-2 mt-1">
          <MiniProbs
            ph={frozen.prob_home}
            pd={frozen.prob_draw}
            pa={frozen.prob_away}
            winner={frozen.predicted_winner}
          />
          <div className="flex gap-3 text-[10px]">
            <div className={`flex flex-col items-center gap-0.5 ${btts_correct ? 'text-green-400' : 'text-gray-500'}`}>
              <span>BTTS</span>
              <span className="font-bold">{pct(frozen.btts_yes)}</span>
              <span>{btts_correct ? '✓' : '✗'}</span>
            </div>
            <div className={`flex flex-col items-center gap-0.5 ${over_2_5_correct ? 'text-green-400' : 'text-gray-500'}`}>
              <span>O2.5</span>
              <span className="font-bold">{pct(frozen.over_2_5)}</span>
              <span>{over_2_5_correct ? '✓' : '✗'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Pending match row ────────────────────────────────────────────────────────
function PendingRow({ match }) {
  const { home_team, away_team, date, stage, group, frozen } = match
  return (
    <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-3 sm:p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{formatDate(date)}</span>
          <span>·</span>
          <span>{group ? `Gr. ${group}` : stageLabel(stage)}</span>
        </div>
        {frozen?.predicted_winner && <OutcomeBadge winner={frozen.predicted_winner} />}
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-xl">{flag(home_team)}</span>
          <span className="text-sm font-medium text-white truncate">{home_team}</span>
        </div>

        {frozen ? (
          <MiniProbs
            ph={frozen.prob_home}
            pd={frozen.prob_draw}
            pa={frozen.prob_away}
            winner={frozen.predicted_winner}
          />
        ) : (
          <span className="text-xs text-gray-600 px-3">vs</span>
        )}

        <div className="flex items-center gap-1.5 flex-1 min-w-0 justify-end">
          <span className="text-sm font-medium text-white truncate text-right">{away_team}</span>
          <span className="text-xl">{flag(away_team)}</span>
        </div>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function LiveTracking() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState('completed')

  const { data, isLoading, error } = useQuery({
    queryKey: ['tracking'],
    queryFn: api.tracking,
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  })

  const refreshMut = useMutation({
    mutationFn: api.trackingRefresh,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tracking'] }),
  })

  const freezeMut = useMutation({
    mutationFn: api.trackingFreeze,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tracking'] }),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan-400 animate-pulse text-sm">Se încarcă tracking-ul…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
          Eroare la încărcarea tracking-ului: {error.message}
        </div>
      </div>
    )
  }

  const { completed = [], pending = [], metrics = {} } = data ?? {}
  const hasCompleted = completed.length > 0

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      {/* Title */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Live Tracking</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Predicții înghețate vs. rezultate reale · <span className="text-cyan-400">DC+Isotonic</span>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => freezeMut.mutate()}
            disabled={freezeMut.isPending}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-navy-700 text-gray-300 hover:text-white hover:bg-navy-600 transition-colors disabled:opacity-50"
          >
            {freezeMut.isPending ? '…' : '🔒 Freeze'}
          </button>
          <button
            onClick={() => refreshMut.mutate()}
            disabled={refreshMut.isPending}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition-colors disabled:opacity-50"
          >
            {refreshMut.isPending ? '…' : '↻ Refresh rezultate'}
          </button>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <MetricCard
          label="Meciuri jucate"
          value={metrics.matches_played ?? 0}
          highlight
        />
        <MetricCard
          label="Predicții corecte"
          value={hasCompleted ? `${metrics.correct_picks}/${metrics.matches_played}` : '—'}
          sub={hasCompleted ? pct(metrics.accuracy) : undefined}
          highlight={hasCompleted}
        />
        <MetricCard
          label="Log-Loss"
          value={metrics.log_loss != null ? metrics.log_loss.toFixed(4) : '—'}
          sub="↓ mai mic = mai bun"
          warn={metrics.log_loss != null && metrics.log_loss > 1.0}
        />
        <MetricCard
          label="Brier Score"
          value={metrics.brier != null ? metrics.brier.toFixed(4) : '—'}
          sub="↓ mai mic = mai bun"
        />
      </div>

      {/* Markets metrics */}
      {hasCompleted && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          <MetricCard
            label="BTTS Hit-rate"
            value={metrics.btts_hit_rate != null ? pct(metrics.btts_hit_rate) : '—'}
            sub={`din ${metrics.matches_played} meciuri`}
          />
          <MetricCard
            label="Over 2.5 Hit-rate"
            value={metrics.over_2_5_hit_rate != null ? pct(metrics.over_2_5_hit_rate) : '—'}
            sub={`din ${metrics.matches_played} meciuri`}
          />
        </div>
      )}

      {/* Small sample warning */}
      {metrics.small_sample_warning && hasCompleted && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-yellow-500/10 border border-yellow-500/25 text-yellow-300 text-xs">
          ⚠ Eșantion mic ({metrics.matches_played} meciuri) — cifrele se stabilizează pe parcursul turneului.
        </div>
      )}

      {/* Disclaimer */}
      <p className="text-xs text-gray-600 mb-5">
        Predicțiile au fost generate de modelul DC+Isotonic și înghețate înaintea meciurilor.
        Proiect educațional — nu este un sfat de pariere.
        {metrics.without_prediction > 0 && ` · ${metrics.without_prediction} meciuri jucate fără predicție înghețată.`}
      </p>

      {/* No data state */}
      {!hasCompleted && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-8 text-center mb-6">
          <p className="text-3xl mb-3">🏆</p>
          <p className="text-white font-medium mb-1">Niciun meci finalizat încă</p>
          <p className="text-sm text-gray-400 mb-4">
            Adaugă rezultate prin pagina Admin sau apasă „Refresh rezultate" pentru a prelua din surse externe.
          </p>
          <a
            href="http://localhost:8000/admin"
            target="_blank"
            rel="noreferrer"
            className="inline-block px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-300 text-sm hover:bg-cyan-500/30 transition-colors"
          >
            Deschide Admin →
          </a>
        </div>
      )}

      {/* Tab bar */}
      {(hasCompleted || pending.length > 0) && (
        <div className="flex gap-1 mb-4 bg-navy-800 rounded-xl p-1">
          <button
            onClick={() => setActiveTab('completed')}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'completed'
                ? 'bg-navy-700 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Jucate ({completed.length})
          </button>
          <button
            onClick={() => setActiveTab('pending')}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'pending'
                ? 'bg-navy-700 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Urmează ({pending.length})
          </button>
        </div>
      )}

      {/* Completed matches */}
      {activeTab === 'completed' && (
        <div className="flex flex-col gap-3">
          {completed.length === 0 ? (
            <p className="text-center text-gray-500 text-sm py-8">
              Niciun meci finalizat cu predicție înghețată.
            </p>
          ) : (
            completed.map((m) => <CompletedRow key={m.match_id} match={m} />)
          )}
        </div>
      )}

      {/* Pending matches */}
      {activeTab === 'pending' && (
        <div className="flex flex-col gap-2">
          {pending.length === 0 ? (
            <p className="text-center text-gray-500 text-sm py-8">
              Niciun meci în așteptare.
            </p>
          ) : (
            pending.map((m) => <PendingRow key={m.match_id} match={m} />)
          )}
        </div>
      )}
    </div>
  )
}
