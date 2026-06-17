import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import MatchCard from '../components/MatchCard.jsx'
import LoadingSpinner, { ErrorMsg } from '../components/LoadingSpinner.jsx'
import { flag } from '../utils/flags.js'
import { GROUP_COLORS } from '../utils/flags.js'

const GROUPS = ['A','B','C','D','E','F','G','H','I','J','K','L']

function GroupTab({ id, active, onClick }) {
  const color = GROUP_COLORS[id] ?? '#22D3EE'
  return (
    <button
      onClick={() => onClick(id)}
      className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition-all ${
        active
          ? 'text-white'
          : 'text-gray-400 hover:text-white'
      }`}
      style={active ? { backgroundColor: color + '30', color } : {}}
    >
      {id}
    </button>
  )
}

function GroupOverview({ groupId, onSelect }) {
  const { data, isLoading } = useQuery({
    queryKey: ['matches', 'group', groupId],
    queryFn: () => api.matches({ group: groupId, limit: 20 }),
  })

  const matches = data?.matches ?? []
  const teams = [...new Set(matches.flatMap(m => [m.home_team, m.away_team]))].filter(t => t !== 'TBD')
  const color = GROUP_COLORS[groupId] ?? '#22D3EE'

  return (
    <div
      className="card p-4 cursor-pointer hover:scale-[1.01] transition-transform"
      onClick={() => onSelect(groupId)}
    >
      <div
        className="text-sm font-bold mb-3 pb-2 border-b border-navy-700"
        style={{ color }}
      >
        Grupa {groupId}
      </div>
      <div className="space-y-1.5 mb-3">
        {isLoading ? <div className="text-gray-500 text-xs">Se încarcă...</div> :
         teams.map(t => (
           <div key={t} className="flex items-center gap-2 text-sm">
             <span>{flag(t)}</span>
             <span className="text-gray-200">{t}</span>
           </div>
         ))
        }
      </div>
      <button
        className="text-xs font-medium mt-1"
        style={{ color }}
      >
        Vezi meciuri →
      </button>
    </div>
  )
}

function GroupDetail({ groupId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['matches', 'group', groupId],
    queryFn: () => api.matches({ group: groupId, limit: 20 }),
  })

  const matches = data?.matches ?? []

  const md1 = matches.filter(m => m.matchday === 1)
  const md2 = matches.filter(m => m.matchday === 2)
  const md3 = matches.filter(m => m.matchday === 3)

  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMsg message={error.message} />

  return (
    <div className="space-y-6">
      {[['Etapa 1', md1], ['Etapa 2', md2], ['Etapa 3', md3]].map(([label, mds]) =>
        mds.length > 0 && (
          <section key={label}>
            <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">{label}</h3>
            <div className="grid gap-3 md:grid-cols-2">
              {mds.map(m => <MatchCard key={m.match_id} match={m} showGroup={false} />)}
            </div>
          </section>
        )
      )}
    </div>
  )
}

export default function GroupStage() {
  const { groupId: paramGroup } = useParams()
  const navigate = useNavigate()
  const [selected, setSelected] = useState(paramGroup?.toUpperCase() ?? null)

  function handleSelect(id) {
    setSelected(id)
    navigate(`/groups/${id}`, { replace: true })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Faza Grupelor</h1>
        {selected && (
          <button
            onClick={() => { setSelected(null); navigate('/groups', { replace: true }) }}
            className="text-sm text-gray-400 hover:text-white"
          >
            ← Înapoi la grupe
          </button>
        )}
      </div>

      {/* Group tabs */}
      <div className="flex flex-wrap gap-1 mb-6 card p-2">
        {GROUPS.map(g => (
          <GroupTab key={g} id={g} active={selected === g} onClick={handleSelect} />
        ))}
      </div>

      {selected ? (
        <>
          <h2 className="text-xl font-bold mb-4" style={{ color: GROUP_COLORS[selected] }}>
            Grupa {selected}
          </h2>
          <GroupDetail groupId={selected} />
        </>
      ) : (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
          {GROUPS.map(g => (
            <GroupOverview key={g} groupId={g} onSelect={handleSelect} />
          ))}
        </div>
      )}
    </div>
  )
}
