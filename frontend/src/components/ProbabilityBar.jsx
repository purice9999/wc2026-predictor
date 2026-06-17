import { pct } from '../utils/format.js'

export default function ProbabilityBar({ home, draw, away, homeTeam, awayTeam, compact = false }) {
  const h = Math.round(home * 100)
  const d = Math.round(draw * 100)
  const a = Math.round(away * 100)

  return (
    <div className="w-full">
      {/* Labels */}
      {!compact && (
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span className="text-cyan-400 font-medium">{homeTeam}</span>
          <span>Egal</span>
          <span className="text-amber-400 font-medium">{awayTeam}</span>
        </div>
      )}

      {/* Bar */}
      <div className="h-2 w-full flex rounded-full overflow-hidden gap-0.5">
        <div style={{ width: `${h}%` }} className="bg-cyan-500 transition-all duration-500" />
        <div style={{ width: `${d}%` }} className="bg-gray-500 transition-all duration-500" />
        <div style={{ width: `${a}%` }} className="bg-amber-500 transition-all duration-500" />
      </div>

      {/* Percentages */}
      <div className="flex justify-between text-xs mt-1 font-semibold">
        <span className="text-cyan-400">{h}%</span>
        <span className="text-gray-400">{d}%</span>
        <span className="text-amber-400">{a}%</span>
      </div>
    </div>
  )
}
