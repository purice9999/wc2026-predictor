import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client.js'
import { flag } from '../utils/flags.js'
import { pct, formatDateLong, stageLabel, impliedOdds } from '../utils/format.js'
import ProbabilityBar from '../components/ProbabilityBar.jsx'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'

function Market({ label, value, highlight }) {
  return (
    <div className={`card p-3 text-center ${highlight ? 'border-cyan-500/40' : ''}`}>
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-lg font-bold ${highlight ? 'text-cyan-400' : 'text-white'}`}>
        {pct(value)}
      </div>
      <div className="text-xs text-gray-500">cota {impliedOdds(value)}</div>
    </div>
  )
}

function ScoreGrid({ scorelines }) {
  const top = scorelines?.slice(0, 9) ?? []
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">Scoruri Probabile</h3>
      <div className="grid grid-cols-3 gap-2">
        {top.map(s => (
          <div key={`${s.home}-${s.away}`} className="bg-navy-900 rounded-lg p-2 text-center">
            <div className="text-base font-bold text-white">{s.home}–{s.away}</div>
            <div className="text-xs text-cyan-400">{pct(s.prob)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function EloBar({ home, away, homeTeam, awayTeam }) {
  const max = Math.max(home, away, 1800)
  const min = Math.min(home, away, 1200)
  const range = max - min

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">Rating Elo</h3>
      <div className="space-y-3">
        {[[homeTeam, home, 'text-cyan-400'], [awayTeam, away, 'text-amber-400']].map(([team, elo, cls]) => (
          <div key={team}>
            <div className="flex justify-between text-xs mb-1">
              <span className={`font-medium ${cls}`}>{flag(team)} {team}</span>
              <span className="text-gray-300 font-bold">{Math.round(elo)}</span>
            </div>
            <div className="h-2 bg-navy-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${cls.replace('text-', 'bg-')}`}
                style={{ width: `${range > 0 ? ((elo - min) / range) * 80 + 20 : 60}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ResultBanner({ result, match }) {
  if (!result) return null
  const correct = result.correct
  return (
    <div className={`rounded-xl p-4 mb-6 border ${
      correct === true
        ? 'bg-green-500/10 border-green-500/30 text-green-400'
        : correct === false
        ? 'bg-red-500/10 border-red-500/30 text-red-400'
        : 'bg-navy-800 border-navy-700 text-white'
    }`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wider opacity-70 mb-1">Rezultat Final</div>
          <div className="text-3xl font-bold">
            {result.home_score} – {result.away_score}
          </div>
        </div>
        <div className="text-right">
          {correct === true && <div className="text-2xl">✓</div>}
          {correct === false && <div className="text-2xl">✗</div>}
          <div className="text-xs opacity-70 mt-1">
            {correct === true ? 'Predicție corectă' : correct === false ? 'Predicție greșită' : 'Fără predicție'}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MatchDetail() {
  const { matchId } = useParams()

  const { data: match, isLoading: mLoading, error: mError } = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => api.match(matchId),
  })

  const isTBD = match?.home_team === 'TBD' || match?.away_team === 'TBD'

  const { data: pred, isLoading: pLoading } = useQuery({
    queryKey: ['predict', matchId],
    queryFn: () => api.predict(matchId),
    enabled: !!match && !isTBD,
  })

  const { data: result } = useQuery({
    queryKey: ['result', matchId],
    queryFn: () => api.result(matchId),
  })

  if (mLoading) return <LoadingSpinner size="lg" />
  if (mError) return <ErrorMsg message={mError.message} />
  if (!match) return null

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Back */}
      <Link
        to={match.group ? `/groups/${match.group}` : '/bracket'}
        className="text-sm text-gray-400 hover:text-white flex items-center gap-1"
      >
        ← {match.group ? `Grupa ${match.group}` : 'Bracket Knockout'}
      </Link>

      {/* Header */}
      <div className="card p-6">
        <div className="text-center mb-4">
          <span className="badge bg-cyan-500/10 text-cyan-400">{stageLabel(match.stage)}</span>
          {match.group && <span className="badge bg-navy-700 text-gray-300 ml-2">Grupa {match.group}</span>}
          {match.matchday && <span className="badge bg-navy-700 text-gray-300 ml-2">Etapa {match.matchday}</span>}
        </div>

        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex-1 text-center">
            <div className="text-4xl mb-2">{flag(match.home_team)}</div>
            <div className="font-bold text-white">{match.home_team}</div>
          </div>

          <div className="text-center flex-shrink-0">
            {result ? (
              <div className="text-3xl font-extrabold text-white">
                {result.home_score} – {result.away_score}
              </div>
            ) : (
              <div>
                {pred ? (
                  <div className="text-2xl font-bold text-white/60">
                    {pred.most_likely_score.home}:{pred.most_likely_score.away}
                  </div>
                ) : (
                  <div className="text-white/40 text-2xl">vs</div>
                )}
                {pred && <div className="text-xs text-gray-500 mt-1">scor probabil</div>}
              </div>
            )}
          </div>

          <div className="flex-1 text-center">
            <div className="text-4xl mb-2">{flag(match.away_team)}</div>
            <div className="font-bold text-white">{match.away_team}</div>
          </div>
        </div>

        <div className="text-center text-xs text-gray-400 space-y-0.5">
          <div>{formatDateLong(match.date)} · {match.time}</div>
          <div>{match.stadium}, {match.city}</div>
        </div>
      </div>

      {/* Result banner */}
      {result && (
        <ResultBanner result={result} match={match} />
      )}

      {/* Prediction */}
      {isTBD && (
        <div className="card p-6 text-center text-gray-400">
          <div className="text-3xl mb-2">⏳</div>
          <div className="font-medium">Echipele nu au fost determinate încă</div>
          <div className="text-sm mt-1">Predicțiile vor fi disponibile după faza grupelor.</div>
        </div>
      )}

      {pLoading && !isTBD && <LoadingSpinner />}

      {pred && (
        <>
          {/* Main probability */}
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Probabilitate Rezultat</h3>
            <ProbabilityBar
              home={pred.prob_home}
              draw={pred.prob_draw}
              away={pred.prob_away}
              homeTeam={match.home_team}
              awayTeam={match.away_team}
            />

            {/* xG */}
            <div className="mt-4 pt-4 border-t border-navy-700 flex justify-around text-center">
              <div>
                <div className="text-2xl font-bold text-cyan-400">{pred.xg_home.toFixed(2)}</div>
                <div className="text-xs text-gray-400">xG {match.home_team}</div>
              </div>
              <div className="text-gray-600 flex items-center">vs</div>
              <div>
                <div className="text-2xl font-bold text-amber-400">{pred.xg_away.toFixed(2)}</div>
                <div className="text-xs text-gray-400">xG {match.away_team}</div>
              </div>
            </div>
          </div>

          {/* Elo */}
          <EloBar
            home={pred.elo_home}
            away={pred.elo_away}
            homeTeam={match.home_team}
            awayTeam={match.away_team}
          />

          {/* Goal markets */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Piețe Goluri</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Market label="BTTS Da" value={pred.btts_yes} highlight={pred.btts_yes > 0.5} />
              <Market label="BTTS Nu" value={pred.btts_no} />
              <Market label="Peste 2.5" value={pred.over_2_5} highlight={pred.over_2_5 > 0.5} />
              <Market label="Sub 2.5" value={pred.under_2_5} />
              <Market label="Peste 1.5" value={pred.over_1_5} />
              <Market label="Sub 1.5" value={pred.under_1_5} />
              <Market label="Peste 3.5" value={pred.over_3_5} />
              <Market label="Sub 3.5" value={pred.under_3_5} />
            </div>
          </div>

          {/* Clean sheets + shots */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Apărare &amp; Suturi</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Market label={`Poartă neviolată — ${match.home_team}`} value={pred.cs_home} />
              <Market label={`Poartă neviolată — ${match.away_team}`} value={pred.cs_away} />
              <div className="card p-3 text-center">
                <div className="text-xs text-gray-400 mb-1">SOT {match.home_team}</div>
                <div className="text-lg font-bold text-cyan-400">{pred.sot_home.toFixed(1)}</div>
                <div className="text-xs text-gray-500">suturi estimate</div>
              </div>
              <div className="card p-3 text-center">
                <div className="text-xs text-gray-400 mb-1">SOT {match.away_team}</div>
                <div className="text-lg font-bold text-amber-400">{pred.sot_away.toFixed(1)}</div>
                <div className="text-xs text-gray-500">suturi estimate</div>
              </div>
            </div>
          </div>

          {/* Scorelines */}
          <ScoreGrid scorelines={pred.top_scorelines} />

          {/* Value bet */}
          {pred.value_bet && (
            <div className="card p-4 border-amber-500/30">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-amber-400">💡</span>
                <span className="text-sm font-semibold text-amber-400">Value Bet</span>
              </div>
              <div className="text-sm text-gray-300">{pred.value_bet}</div>
            </div>
          )}

          {/* Explanation */}
          <div className="card p-4">
            <div className="text-xs text-gray-400 mb-2 font-medium">Explicație model</div>
            <div className="text-sm text-gray-300 leading-relaxed">{pred.explanation}</div>
            <div className="text-xs text-gray-600 mt-2">Model: {pred.model_used}</div>
          </div>
        </>
      )}

      <p className="text-xs text-gray-600 text-center pb-2">
        Proiect educațional · Nu este un instrument de pariuri
      </p>
    </div>
  )
}
