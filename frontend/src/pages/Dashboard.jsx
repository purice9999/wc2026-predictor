import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import MatchCard from '../components/MatchCard.jsx'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'

const TODAY = '2026-06-16'

function ModelInfoBar() {
  const { data } = useQuery({
    queryKey: ['model-info'],
    queryFn: api.modelInfo,
    staleTime: 300_000,
  })
  if (!data) return null
  const w = data.weights
  const activeComponents = [
    { label: 'Dixon-Coles', value: w.dixon_coles },
    { label: 'Elo', value: w.elo },
    { label: 'XGBoost', value: w.xgboost },
  ].filter(c => c.value > 0)
  const calLabel = data.calibration
    ? data.calibration.charAt(0).toUpperCase() + data.calibration.slice(1)
    : null

  return (
    <div className="card p-3 flex flex-wrap items-center gap-4 text-xs">
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
        <span className="text-gray-300 font-medium">Model activ:</span>
        <span className="text-cyan-400 font-bold">{data.ensemble}</span>
      </div>
      <div className="flex items-center gap-2 text-gray-400">
        {activeComponents.map((c, i) => (
          <span key={c.label} className="flex items-center gap-2">
            {i > 0 && <span className="text-navy-600">·</span>}
            <span className="text-white font-semibold">{Math.round(c.value * 100)}%</span>
            {c.label}
          </span>
        ))}
      </div>
      {data.calibrated && calLabel && (
        <span className="badge bg-purple-500/10 text-purple-400 ml-auto">
          ✓ {calLabel} calibrat
        </span>
      )}
    </div>
  )
}

function AccuracyWidget() {
  const { data } = useQuery({ queryKey: ['accuracy'], queryFn: api.accuracy })
  if (!data || data.total === 0) return null

  const pct = data.with_prediction > 0
    ? Math.round((data.correct / data.with_prediction) * 100)
    : 0

  return (
    <div className="card p-4 flex items-center gap-4">
      <div className="w-16 h-16 rounded-full border-4 border-cyan-500 flex items-center justify-center flex-shrink-0">
        <span className="text-xl font-bold text-cyan-400">{pct}%</span>
      </div>
      <div>
        <div className="text-sm font-semibold text-white">Acuratețe Predicții</div>
        <div className="text-xs text-gray-400 mt-0.5">
          {data.correct} corecte din {data.with_prediction} prezise · {data.total} meciuri înregistrate
        </div>
      </div>
    </div>
  )
}

function HeroSection() {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-navy-800 to-navy-900 border border-navy-700 p-6 mb-6">
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-4 right-4 text-9xl">🏆</div>
      </div>
      <div className="relative">
        <div className="badge bg-amber-500/20 text-amber-400 mb-3">FIFA World Cup 2026</div>
        <h1 className="text-3xl font-extrabold text-white mb-1">
          Predictor{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
            WC 2026
          </span>
        </h1>
        <p className="text-gray-400 text-sm mb-4">
          Dixon-Coles + Isotonic · 48 echipe · 104 meciuri · 3 gazde
        </p>
        <div className="flex gap-3">
          <Link to="/groups" className="btn-primary">Explorează Grupele</Link>
          <Link to="/bracket" className="btn-secondary">Bracket Knockout</Link>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: todayData, isLoading: todayLoading, error: todayError } = useQuery({
    queryKey: ['matches', 'today'],
    queryFn: () => api.matches({ date_from: TODAY, date_to: TODAY, limit: 20 }),
  })

  const { data: upcomingData, isLoading: upcomingLoading } = useQuery({
    queryKey: ['matches', 'upcoming'],
    queryFn: () => api.matches({ status: 'scheduled', limit: 12 }),
  })

  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ['matches', 'recent'],
    queryFn: () => api.matches({ status: 'finished', limit: 8 }),
  })

  const todayMatches = todayData?.matches ?? []
  const upcomingMatches = upcomingData?.matches ?? []
  const recentMatches = recentData?.matches?.slice().reverse() ?? []

  return (
    <div className="space-y-6">
      <HeroSection />
      <ModelInfoBar />
      <AccuracyWidget />

      {/* Today */}
      {(todayLoading || todayMatches.length > 0) && (
        <section>
          <h2 className="section-title flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse inline-block" />
            Meciuri Astăzi
          </h2>
          {todayLoading ? <LoadingSpinner /> :
           todayError ? <ErrorMsg message={todayError.message} /> :
           todayMatches.length === 0 ? <p className="text-gray-500 text-sm">Niciun meci astăzi.</p> : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {todayMatches.map(m => <MatchCard key={m.match_id} match={m} />)}
            </div>
          )}
        </section>
      )}

      {/* Upcoming */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title mb-0">Meciuri Programate</h2>
          <Link to="/groups" className="text-xs text-cyan-400 hover:underline">Vezi toate →</Link>
        </div>
        {upcomingLoading ? <LoadingSpinner /> : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {upcomingMatches.map(m => <MatchCard key={m.match_id} match={m} />)}
          </div>
        )}
      </section>

      {/* Recent results */}
      {recentMatches.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title mb-0">Rezultate Recente</h2>
            <Link to="/history" className="text-xs text-cyan-400 hover:underline">Toate rezultatele →</Link>
          </div>
          {recentLoading ? <LoadingSpinner /> : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {recentMatches.map(m => <MatchCard key={m.match_id} match={m} />)}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
