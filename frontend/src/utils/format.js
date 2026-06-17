export function pct(p) {
  return `${Math.round(p * 100)}%`
}

export function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('ro-RO', { weekday: 'short', day: 'numeric', month: 'short' })
}

export function formatDateLong(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

export function stageLabel(stage) {
  const map = {
    'Group Stage': 'Grupe',
    'Round of 32': 'R32',
    'Round of 16': 'R16',
    'Quarter-Finals': 'Sferturi',
    'Semi-Finals': 'Semifinale',
    'Third Place': 'Locul 3',
    'Final': 'Finala',
  }
  return map[stage] ?? stage
}

export function winnerLabel(w) {
  if (w === 'home') return 'V acasă'
  if (w === 'away') return 'V deplasare'
  return 'Egal'
}

export function outcomeLabel(w) {
  if (w === 'home') return '1'
  if (w === 'draw') return 'X'
  if (w === 'away') return '2'
  return '?'
}

export function impliedOdds(p) {
  if (!p || p <= 0) return '—'
  return (1 / p).toFixed(2)
}
