import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

const navItems = [
  {
    section: 'Markets',
    links: [
      {
        to: '/markets',
        label: 'All Events',
        icon: (
          <svg width="15" height="15" viewBox="0 0 15 15" fill="currentColor">
            <path d="M1 2h13v2H1zM1 6h9v2H1zM1 10h11v2H1z" opacity=".6" />
          </svg>
        ),
      },
    ],
  },
  {
    section: 'Trading',
    links: [
      {
        to: '/p2p',
        label: 'P2P Direct',
        icon: (
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M2 7.5h11M9 3.5l4 4-4 4M6 11.5l-4-4 4-4"
              stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        ),
      },
      {
        to: '/pool',
        label: 'Pool Market',
        icon: (
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <circle cx="7.5" cy="7.5" r="5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M7.5 4.5v3l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        ),
      },
    ],
  },
  {
    section: 'Account',
    links: [
      {
        to: '/portfolio',
        label: 'Portfolio',
        icon: (
          <svg width="15" height="15" viewBox="0 0 15 15" fill="currentColor">
            <rect x="1" y="1" width="5" height="5" rx="1" opacity=".6" />
            <rect x="9" y="1" width="5" height="5" rx="1" opacity=".6" />
            <rect x="1" y="9" width="5" height="5" rx="1" opacity=".6" />
            <rect x="9" y="9" width="5" height="5" rx="1" opacity=".6" />
          </svg>
        ),
      },
    ],
  },
]

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initials = user?.email?.slice(0, 2).toUpperCase() ?? 'CD'
  const balance = parseFloat(user?.balance_available ?? '0').toFixed(2)

  return (
    <aside
      className="flex flex-col w-56 min-h-screen flex-shrink-0"
      style={{
        background: '#0d1117',
        borderRight: '1px solid rgba(0,212,255,0.08)',
        position: 'relative',
      }}
    >
      {/* Sidebar glow line */}
      <div
        className="absolute top-0 right-0 w-px h-full pointer-events-none"
        style={{
          background: 'linear-gradient(to bottom, transparent, rgba(0,212,255,0.3) 35%, rgba(0,212,255,0.3) 65%, transparent)',
          opacity: 0.35,
        }}
      />

      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6">
        <div
          className="w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0"
          style={{
            background: 'rgba(0,212,255,0.08)',
            border: '1px solid rgba(0,212,255,0.2)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L4 7v5c0 5 4 9 8 10 4-1 8-5 8-10V7L12 2z"
              stroke="#00d4ff" strokeWidth="1.5" fill="rgba(0,212,255,0.08)" />
            <path d="M9 12l2 2 4-4"
              stroke="#00d4ff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <div className="text-sm font-black tracking-wide">CyberDuel</div>
          <div
            className="text-xs tracking-widest"
            style={{ color: '#00d4ff', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px', opacity: 0.65 }}
          >
            PROTOCOL
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 flex flex-col gap-5">
        {navItems.map((section) => (
          <div key={section.section}>
            <div
              className="px-2 mb-1 uppercase tracking-widest"
              style={{ fontSize: '9px', color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
            >
              {section.section}
            </div>
            {section.links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className="flex items-center gap-2 px-2 py-2 rounded-lg text-sm font-semibold transition-all"
                style={({ isActive }) => ({
                  color: isActive ? '#00d4ff' : '#4a5568',
                  background: isActive ? 'rgba(0,212,255,0.08)' : 'transparent',
                  position: 'relative',
                })}
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <div
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 rounded-r"
                        style={{
                          height: '55%',
                          background: '#00d4ff',
                          boxShadow: '0 0 8px rgba(0,212,255,0.5)',
                        }}
                      />
                    )}
                    <span style={{ color: isActive ? '#00d4ff' : '#4a5568' }}>
                      {link.icon}
                    </span>
                    {link.label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* User */}
      <div
        className="mx-3 mb-4 p-3 rounded-lg cursor-pointer transition-all"
        style={{ borderTop: '1px solid rgba(0,212,255,0.08)' }}
        onClick={handleLogout}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,51,102,0.06)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        title="Click to disconnect"
      >
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-black"
            style={{
              background: 'rgba(0,212,255,0.12)',
              border: '1px solid rgba(0,212,255,0.3)',
              color: '#00d4ff',
            }}
          >
            {initials}
          </div>
          <div className="min-w-0">
            <div className="text-xs font-bold truncate">{user?.email?.split('@')[0]}</div>
            <div
              className="text-xs"
              style={{ color: '#00d4ff', fontFamily: 'JetBrains Mono, monospace' }}
            >
              {balance} CR
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}