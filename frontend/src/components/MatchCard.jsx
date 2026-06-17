import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client.js'
import { flag } from '../utils/flags.js'
import { formatDate, stageLabel } from '../utils/format.js'
import ProbabilityBar from './ProbabilityBar.jsx'

function StatusBadge({ status }) {
  if (status === 'live') return <span className="badge bg-red-500/20 text-red-400 animate-pulse">● LIVE</span>
  if (status === 'finished') return <span className="badge bg-green-500/10 text-green-400">Terminat</span>
  return <span className="badge bg-navy-700 text-gray-400">Programat</span>
}

function ResultDisplay({ result }) {
  if (!result) return null
  const correct = result.correct
  return (
    <div className={`text-center mt-2 py-1.5 rounded-lg text-sm font-bold ${
      correct === true ? 'bg-green-500/10 text-green-400' :
      correct === false ? 'bg-red-500/10 text-red-400' :
      'bg-navy-700 text-white'
    }`}>
      {result.home_score} – {result.away_score}
      {correct === true && <span className="ml-2 text-xs">✓ corect</span>}
      {correct === false && <span className="ml-2 text-xs">✗ greșit</span>}
    </div>
  )
}

export default function MatchCard({ match, showGroup = true }) {
  const { data: pred } = useQuery({
    queryKey: ['predict', match.match_id],
    queryFn: () => api.predict(match.match_id),
    enabled: match.home_team !== 'TBD' && match.away_team !== 'TBD',
    staleTime: 60_000,
  })

  const { data: result } = useQuery({
    queryKey: ['result', match.match_id],
    queryFn: () => api.result(match.match_id),
    staleTime: 30_000,
  })

  const isTBD = match.home_team === 'TBD' || match.away_team === 'TBD'

  return (
    <Link
      to={`/match/${match.match_id}`}
      className="card p-4 block hover:border-cyan-500/40 hover:bg-navy-800/80 transition-all duration-200 group"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          {showGroup && match.group && (
            <span className="badge bg-cyan-500/10 text-cyan-400">Grupa {match.group}</span>
          )}
          <span>{stageLabel(match.stage)}</span>
          {match.matchday && <span>MD{match.matchday}</span>}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span>{formatDate(match.date)}</span>
          <span>{match.time}</span>
          <StatusBadge status={match.status} />
        </div>
      </div>

      {/* Teams */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 flex items-center gap-2 min-w-0">
          <span className="text-2xl flex-shrink-0">{flag(match.home_team)}</span>
          <span className="font-semibold text-white text-sm truncate group-hover:text-cyan-400 transition-colors">
            {match.home_team}
          </span>
        </div>

        {result ? (
          <div className="flex-shrink-0 text-center">
            <div className="text-xl font-bold text-white">
              {result.home_score} – {result.away_score}
            </div>
            {result.correct === true && <div className="text-xs text-green-400">✓ corect</div>}
            {result.correct === false && <div className="text-xs text-red-400">✗ greșit</div>}
          </div>
        ) : (
          <div className="flex-shrink-0 text-center">
            {pred ? (
              <div className="text-base font-bold text-gray-300">
                {pred.most_likely_score.home}:{pred.most_likely_score.away}
              </div>
            ) : (
              <div className="text-gray-500 text-lg">vs</div>
            )}
            {!isTBD && <div className="text-xs text-gray-500 mt-0.5">prognozat</div>}
          </div>
        )}

        <div className="flex-1 flex items-center gap-2 min-w-0 flex-row-reverse">
          <span className="text-2xl flex-shrink-0">{flag(match.away_team)}</span>
          <span className="font-semibold text-white text-sm truncate text-right group-hover:text-amber-400 transition-colors">
            {match.away_team}
          </span>
        </div>
      </div>

      {/* Probability bar */}
      {pred && !isTBD && (
        <div className="mt-3">
          <ProbabilityBar
            home={pred.prob_home}
            draw={pred.prob_draw}
            away={pred.prob_away}
            homeTeam={match.home_team}
            awayTeam={match.away_team}
            compact
          />
        </div>
      )}

      {/* Venue */}
      <div className="mt-2 text-xs text-gray-500 text-center truncate">
        {match.stadium}, {match.city}
      </div>
    </Link>
  )
}
