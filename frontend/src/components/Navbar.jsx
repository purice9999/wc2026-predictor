import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/groups', label: 'Grupe' },
  { to: '/bracket', label: 'Bracket' },
  { to: '/tracking', label: '📊 Tracking' },
  { to: '/history', label: 'Rezultate' },
  { to: '/slip', label: 'Bilet' },
  { to: '/model', label: '🧠 Model' },
]

export default function Navbar() {
  return (
    <nav className="bg-navy-900 border-b border-navy-700 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <NavLink to="/" className="flex items-center gap-2">
          <span className="text-2xl">🏆</span>
          <span className="font-bold text-white text-sm leading-tight">
            WC 2026<br />
            <span className="text-cyan-400 text-xs font-medium">Predictor</span>
          </span>
        </NavLink>

        <div className="flex items-center gap-1">
          {links.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'text-gray-400 hover:text-white hover:bg-navy-700'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
          <a
            href="http://localhost:8000/admin"
            target="_blank"
            rel="noreferrer"
            className="ml-2 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-500 hover:text-white hover:bg-navy-700 transition-colors"
          >
            Admin
          </a>
        </div>
      </div>
    </nav>
  )
}
