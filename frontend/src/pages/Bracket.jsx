import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { flag } from '../utils/flags.js'
import { formatDate } from '../utils/format.js'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'

const STAGE_ORDER = ['Round of 32', 'Round of 16', 'Quarter-Finals', 'Semi-Finals', 'Third Place', 'Final']
const STAGE_LABELS = {
  'Round of 32': 'Optimi de Finală (R32)',
  'Round of 16': 'Șaisprezecimi (R16)',
  'Quarter-Finals': 'Sferturi de Finală',
  'Semi-Finals': 'Semifinale',
  'Third Place': 'Locul 3',
  'Final': 'Marea Finală',
}

function MatchSlot({ match }) {
  const isTBD = match.home_team === 'TBD' || match.away_team === 'TBD'

  const { data: pred } = useQuery({
    queryKey: ['predict', match.match_id],
    queryFn: () => api.predict(match.match_id),
    enabled: !isTBD,
    staleTime: 60_000,
  })

  return (
    <Link
      to={`/match/${match.match_id}`}
      className="card p-3 block hover:border-cyan-500/40 transition-all text-sm"
    >
      <div className="text-xs text-gray-500 mb-2 flex justify-between">
        <span>{formatDate(match.date)}</span>
        <span>{match.city}</span>
      </div>

      {['home', 'away'].map(side => {
        const team = match[`${side}_team`]
        const isFav = pred && (
          side === 'home' ? pred.prob_home >= pred.prob_away
            : pred.prob_away > pred.prob_home
        )
        return (
          <div
            key={side}
            className={`flex items-center gap-2 py-1.5 px-2 rounded-lg mb-1 ${
              isFav && !isTBD ? 'bg-cyan-500/10' : 'bg-navy-900'
            }`}
          >
            <span className="text-base">{flag(team)}</span>
            <span className={`flex-1 font-medium truncate ${
              team === 'TBD' ? 'text-gray-600 italic' : 'text-white'
            }`}>
              {team === 'TBD' ? 'TBD' : team}
            </span>
            {pred && (
              <span className={`text-xs font-semibold ${
                isFav ? 'text-cyan-400' : 'text-gray-500'
              }`}>
                {Math.round((side === 'home' ? pred.prob_home : pred.prob_away) * 100)}%
              </span>
            )}
          </div>
        )
      })}
    </Link>
  )
}

export default function Bracket() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['matches', 'knockout'],
    queryFn: async () => {
      const stages = await Promise.all(
        STAGE_ORDER.map(stage =>
          api.matches({ stage, limit: 50 }).then(r => ({ stage, matches: r.matches }))
        )
      )
      return stages
    },
  })

  if (isLoading) return <LoadingSpinner size="lg" />
  if (error) return <ErrorMsg message={error.message} />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Bracket Knockout</h1>
        <div className="badge bg-amber-500/20 text-amber-400">28 Jun – 19 Iul 2026</div>
      </div>

      <div className="card p-4 mb-6 text-sm text-gray-400 border-amber-500/20">
        <span className="text-amber-400 mr-2">ℹ</span>
        Meciurile knockout vor fi completate după faza grupelor (27 Iunie).
        Predicțiile vor fi disponibile odată ce echipele sunt determinate.
      </div>

      <div className="space-y-8">
        {(data ?? []).map(({ stage, matches }) => {
          if (!matches.length) return null
          return (
            <section key={stage}>
              <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <span className="w-1 h-6 rounded-full bg-cyan-500 inline-block" />
                {STAGE_LABELS[stage] ?? stage}
                <span className="text-sm font-normal text-gray-400">({matches.length} meciuri)</span>
              </h2>

              {stage === 'Final' ? (
                <div className="max-w-sm mx-auto">
                  {matches.map(m => <MatchSlot key={m.match_id} match={m} />)}
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {matches.map(m => <MatchSlot key={m.match_id} match={m} />)}
                </div>
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}
