import { useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

const pageTitles: Record<string, { title: string; sub: string }> = {
  '/markets': { title: 'All Events', sub: 'Esports Prediction Market' },
  '/p2p':     { title: 'P2P Direct', sub: 'Bilateral order matching' },
  '/pool':    { title: 'Pool Market', sub: 'DeFi-style liquidity pools' },
  '/portfolio': { title: 'Portfolio', sub: 'Your positions and history' },
}

export default function Topbar() {
  const { user } = useAuthStore()
  const location = useLocation()

  const page = pageTitles[location.pathname] ?? { title: 'CyberDuel', sub: '' }
  const available = parseFloat(user?.balance_available ?? '0').toFixed(2)
  const locked = parseFloat(user?.balance_locked ?? '0').toFixed(2)

  return (
    <header
      className="flex items-center gap-4 px-6 flex-shrink-0"
      style={{
        height: '54px',
        background: '#0d1117',
        borderBottom: '1px solid rgba(0,212,255,0.08)',
      }}
    >
      {/* Title */}
      <div className="flex-1 flex items-baseline gap-2">
        <span className="text-sm font-black tracking-wide">{page.title}</span>
        <span
          className="text-xs"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
        >
          {page.sub}
        </span>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4">

        <div className="flex flex-col items-end">
          <span
            className="uppercase tracking-widest"
            style={{ fontSize: '9px', color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
          >
            Available
          </span>
          <span
            className="text-sm font-bold"
            style={{ color: '#00d4ff', fontFamily: 'JetBrains Mono, monospace' }}
          >
            {available}
          </span>
        </div>

        <div
          className="w-px h-6"
          style={{ background: 'rgba(0,212,255,0.08)' }}
        />

        <div className="flex flex-col items-end">
          <span
            className="uppercase tracking-widest"
            style={{ fontSize: '9px', color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
          >
            Locked
          </span>
          <span
            className="text-sm font-bold"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
          >
            {locked}
          </span>
        </div>

        <div
          className="w-px h-6"
          style={{ background: 'rgba(0,212,255,0.08)' }}
        />

        {/* Status */}
        <div className="flex items-center gap-1.5">
          <div
            className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
            style={{ background: '#00ff88', boxShadow: '0 0 5px rgba(0,255,136,0.7)' }}
          />
          <span
            className="text-xs"
            style={{ color: '#00ff88', fontFamily: 'JetBrains Mono, monospace' }}
          >
            Live
          </span>
        </div>

      </div>
    </header>
  )
}