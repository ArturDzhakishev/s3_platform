import { NavLink } from 'react-router-dom'

const links = [
  { to: '/',        label: 'Dashboard',  icon: '▦' },
  { to: '/clusters',label: 'Clusters',   icon: '⬡' },
  { to: '/jobs',    label: 'Jobs',       icon: '◎' },
  { to: '/hosts',   label: 'Hosts',      icon: '◉' },
]

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-surface border-r border-border flex flex-col z-10">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-blue/20 border border-blue/30 flex items-center justify-center text-blue text-sm">
            S3
          </div>
          <div>
            <div className="text-sm font-semibold text-text">S3 Platform</div>
            <div className="text-xs text-muted">v0.2.0</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {links.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all duration-150 ${
                isActive
                  ? 'bg-blue/10 text-blue border border-blue/20'
                  : 'text-muted hover:text-text hover:bg-white/5'
              }`
            }
          >
            <span className="font-mono text-base leading-none">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border">
        <div className="text-xs text-muted font-mono">
          API: localhost:8000
        </div>
      </div>
    </aside>
  )
}
