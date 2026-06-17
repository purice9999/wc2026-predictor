import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { flag } from '../utils/flags.js'
import { formatDate, pct } from '../utils/format.js'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'

function OutcomePill({ predicted, actual }) {
  if (predicted == null) return <span className="badge bg-navy-700 text-gray-500">—</span>
  if (predicted === actual) return <span className="badge bg-green-500/20 text-green-400">✓</span>
  return <span className="badge bg-red-500/20 text-red-400">✗</span>
}

function WinnerLabel({ winner }) {
  const map = { home: '1', draw: 'X', away: '2' }
  return <span className="font-mono font-bold">{map[winner] ?? '?'}</span>
}

export default function History() {
  const { data: results, isLoading, error } = useQuery({
    queryKey: ['results'],
    queryFn: api.results,
  })

  const { data: accuracy } = useQuery({
    queryKey: ['accuracy'],
    queryFn: api.accuracy,
  })

  if (isLoading) return <LoadingSpinner size="lg" />
  if (error) return <ErrorMsg message={error.message} />

  const sorted = [...(results ?? [])].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at))

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Rezultate Înregistrate</h1>
        <a
          href="http://localhost:8000/admin"
          target="_blank"
          rel="noreferrer"
          className="btn-secondary text-xs"
        >
          + Adaugă rezultate
        </a>
      </div>

      {/* Stats */}
      {accuracy && accuracy.total > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            ['Total meciuri', accuracy.total, 'text-white'],
            ['Cu predicție', accuracy.with_prediction, 'text-cyan-400'],
            ['Corecte', accuracy.correct, 'text-green-400'],
            ['Acuratețe', `${Math.round(accuracy.accuracy * 100)}%`, 'text-amber-400'],
          ].map(([label, value, cls]) => (
            <div key={label} className="card p-4 text-center">
              <div className={`text-2xl font-bold ${cls}`}>{value}</div>
              <div className="text-xs text-gray-400 mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      {sorted.length === 0 ? (
        <div className="card p-8 text-center text-gray-400">
          <div className="text-4xl mb-3">📋</div>
          <div className="font-medium">Niciun rezultat înregistrat</div>
          <div className="text-sm mt-1">
            Adaugă rezultate via{' '}
            <a href="http://localhost:8000/admin" target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">
              pagina Admin
            </a>
          </div>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-navy-900 text-gray-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Meci</th>
                  <th className="px-4 py-3 text-center">Scor</th>
                  <th className="px-4 py-3 text-center">Rezultat</th>
                  <th className="px-4 py-3 text-center">Predicție</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">H%</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">X%</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">A%</th>
                  <th className="px-4 py-3 text-center">OK</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-700">
                {sorted.map(r => (
                  <tr key={r.match_id} className="hover:bg-navy-900/50 transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/match/${r.match_id}`} className="hover:text-cyan-400 transition-colors">
                        <div className="flex items-center gap-1.5">
                          <span>{flag(r.home_team)}</span>
                          <span className="font-medium text-white">{r.home_team}</span>
                          <span className="text-gray-500 text-xs mx-1">vs</span>
                          <span className="font-medium text-white">{r.away_team}</span>
                          <span>{flag(r.away_team)}</span>
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">{r.stage}</div>
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-center font-bold text-white">
                      {r.home_score}–{r.away_score}
                    </td>
                    <td className="px-4 py-3 text-center text-gray-300">
                      <WinnerLabel winner={r.actual_winner} />
                    </td>
                    <td className="px-4 py-3 text-center text-gray-400">
                      {r.predicted_winner
                        ? <WinnerLabel winner={r.predicted_winner} />
                        : <span className="text-gray-600">—</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-center text-cyan-400 hidden md:table-cell">
                      {r.prob_home > 0 ? pct(r.prob_home) : '—'}
                    </td>
                    <td className="px-4 py-3 text-center text-gray-400 hidden md:table-cell">
                      {r.prob_draw > 0 ? pct(r.prob_draw) : '—'}
                    </td>
                    <td className="px-4 py-3 text-center text-amber-400 hidden md:table-cell">
                      {r.prob_away > 0 ? pct(r.prob_away) : '—'}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <OutcomePill predicted={r.predicted_winner} actual={r.actual_winner} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
