import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { events, markets } from '@/api/endpoints'
import type { Event, Market } from '@/types/api'

// ─── helpers ───────────────────────────────────────────────────────────────

const GAME_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  CS2:      { bg: 'rgba(255,165,0,0.1)',   color: '#ffaa33', border: 'rgba(255,165,0,0.2)' },
  DOTA2:    { bg: 'rgba(255,51,51,0.1)',   color: '#ff5555', border: 'rgba(255,51,51,0.2)' },
  LOL:      { bg: 'rgba(100,149,237,0.1)', color: '#7ba7f0', border: 'rgba(100,149,237,0.2)' },
  VALORANT: { bg: 'rgba(255,70,85,0.12)',  color: '#ff6677', border: 'rgba(255,70,85,0.2)' },
}

const STATUS_CONFIG: Record<string, { color: string; dot: string; glow?: string }> = {
  LIVE:      { color: '#00ff88', dot: '#00ff88', glow: 'rgba(0,255,136,0.7)' },
  OPEN:      { color: '#00d4ff', dot: '#00d4ff', glow: 'rgba(0,212,255,0.6)' },
  SCHEDULED: { color: '#4a5568', dot: '#4a5568' },
  FINISHED:  { color: '#4a5568', dot: '#4a5568' },
  SETTLED:   { color: '#4a5568', dot: '#4a5568' },
}

const GAME_FILTERS = ['All', 'CS2', 'DOTA2', 'LOL', 'VALORANT']
const STATUS_FILTERS = ['All', 'LIVE', 'OPEN', 'SCHEDULED']

function GameBadge({ game }: { game: string }) {
  const c = GAME_COLORS[game] ?? { bg: 'rgba(255,255,255,0.05)', color: '#888', border: 'rgba(255,255,255,0.1)' }
  return (
    <span
      className="text-xs font-bold tracking-widest uppercase px-2 py-0.5 rounded"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}`, fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}
    >
      {game}
    </span>
  )
}

function StatusDot({ status }: { status: string }) {
  const c = STATUS_CONFIG[status] ?? STATUS_CONFIG.SCHEDULED
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="w-1.5 h-1.5 rounded-full"
        style={{
          background: c.dot,
          boxShadow: c.glow ? `0 0 5px ${c.glow}` : 'none',
          animation: status === 'LIVE' ? 'pulse-dot 1.4s infinite' : 'none',
        }}
      />
      <span style={{ color: c.color, fontFamily: 'JetBrains Mono, monospace', fontSize: '10px' }}>
        {status}
      </span>
    </div>
  )
}

// ─── Event Card ─────────────────────────────────────────────────────────────

interface EventCardProps {
  event: Event
  market: Market | undefined
  onClick: () => void
}

function EventCard({ event, market, onClick }: EventCardProps) {
  const [hovered, setHovered] = useState(false)

  // pool bar: просто 50/50 если нет данных, визуализация
  const barA = 55
  const barB = 45

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative rounded-lg p-4 cursor-pointer overflow-hidden"
      style={{
        background: '#111820',
        border: `1px solid ${hovered ? 'rgba(0,212,255,0.22)' : 'rgba(0,212,255,0.08)'}`,
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? '0 8px 28px rgba(0,0,0,0.5)' : 'none',
        transition: 'all 0.22s',
      }}
    >
      {/* top line on hover */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background: 'linear-gradient(90deg, transparent, #00d4ff, transparent)',
          opacity: hovered ? 1 : 0,
          transition: 'opacity 0.3s',
        }}
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <GameBadge game={event.game_type} />
        <StatusDot status={event.status} />
      </div>

      {/* Matchup */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-black">{event.team_a}</span>
        <span
          className="text-xs px-2 py-0.5 rounded mx-2 flex-shrink-0"
          style={{ background: '#1a2535', color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
        >
          vs
        </span>
        <span className="text-sm font-black text-right">{event.team_b}</span>
      </div>

      {/* Pool bar */}
      <div className="h-1.5 rounded-full overflow-hidden flex mb-2" style={{ background: '#1a2535' }}>
        <div
          className="h-full transition-all duration-1000"
          style={{ width: `${barA}%`, background: 'linear-gradient(90deg, #00d4ff, #0099bb)' }}
        />
        <div
          className="h-full transition-all duration-1000"
          style={{ width: `${barB}%`, background: 'linear-gradient(90deg, #7700cc, #aa33ff)' }}
        />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-3">
        <span
          className="text-xs truncate max-w-[140px]"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
        >
          {event.tournament}
        </span>
        <div className="flex gap-1.5 flex-shrink-0">
          {market?.market_mode === 'p2p_direct' || !market ? (
            <span
              className="text-xs font-bold uppercase px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(0,212,255,0.08)', color: '#00d4ff', border: '1px solid rgba(0,212,255,0.15)', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}
            >
              P2P
            </span>
          ) : null}
          {market?.market_mode === 'pool_market' || !market ? (
            <span
              className="text-xs font-bold uppercase px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(0,255,136,0.08)', color: '#00ff88', border: '1px solid rgba(0,255,136,0.15)', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}
            >
              Pool
            </span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function MarketsPage() {
  const navigate = useNavigate()
  const [eventList, setEventList] = useState<Event[]>([])
  const [marketMap, setMarketMap] = useState<Record<number, Market>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [gameFilter, setGameFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const params: Record<string, string> = {}
        if (gameFilter !== 'All') params.game_type = gameFilter
        if (statusFilter !== 'All') params.status = statusFilter

        const { data } = await events.list(params)
        setEventList(data.events)

        const mMap: Record<number, Market> = {}
        await Promise.all(
        data.events.map(async (evt) => {
            try {
            const { data: mks } = await markets.list({ event_id: evt.id })
            if (mks.markets.length > 0) mMap[evt.id] = mks.markets[0]
            } catch { /* skip */ }
        })
        )
        setMarketMap(mMap)
      } catch {
        setError('Failed to load events')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [gameFilter, statusFilter])

  const handleCardClick = (event: Event, market: Market | undefined) => {
    if (!market) return
    if (market.market_mode === 'p2p_direct') {
      navigate(`/p2p?market=${market.id}`)
    } else {
      navigate(`/pool?market=${market.id}`)
    }
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        {/* Game filter */}
        <div
          className="flex gap-1 p-1 rounded-lg"
          style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.08)' }}
        >
          {GAME_FILTERS.map((g) => (
            <button
              key={g}
              onClick={() => setGameFilter(g)}
              className="px-3 py-1.5 rounded-md text-xs font-bold transition-all"
              style={{
                background: gameFilter === g ? 'rgba(0,212,255,0.1)' : 'transparent',
                color: gameFilter === g ? '#00d4ff' : '#4a5568',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              {g}
            </button>
          ))}
        </div>

        {/* Status filter */}
        <div
          className="flex gap-1 p-1 rounded-lg"
          style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.08)' }}
        >
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="px-3 py-1.5 rounded-md text-xs font-bold transition-all"
              style={{
                background: statusFilter === s ? 'rgba(0,212,255,0.1)' : 'transparent',
                color: statusFilter === s ? '#00d4ff' : '#4a5568',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div
            className="text-xs tracking-widest"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
          >
            Loading events...
          </div>
        </div>
      ) : error ? (
        <div
          className="text-sm text-center py-20"
          style={{ color: '#ff3366', fontFamily: 'JetBrains Mono, monospace' }}
        >
          {error}
        </div>
      ) : eventList.length === 0 ? (
        <div
          className="text-sm text-center py-20"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
        >
          No events found
        </div>
      ) : (
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
          {eventList.map((evt) => (
            <EventCard
              key={evt.id}
              event={evt}
              market={marketMap[evt.id]}
              onClick={() => handleCardClick(evt, marketMap[evt.id])}
            />
          ))}
        </div>
      )}
    </div>
  )
}