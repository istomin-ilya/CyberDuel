import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { events, markets, poolMarkets } from '@/api/endpoints'
import { useAuthStore } from '@/store/authStore'
import type { Market, Outcome, PoolState } from '@/types/api'

// ─── Event Selector ───────────────────────────────────────────────────────────

function EventSelector() {
  const navigate = useNavigate()
  const [eventList, setEventList] = useState<any[]>([])
  const [marketMap, setMarketMap] = useState<Record<number, any>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await events.list({ status: 'OPEN' })
        setEventList(data.events)
        const mMap: Record<number, any> = {}
        await Promise.all(data.events.map(async (evt: any) => {
          try {
            const { data: mks } = await markets.list({ event_id: evt.id })
            const pool = mks.markets.find((m: any) => m.market_mode === 'pool_market')
            if (pool) mMap[evt.id] = pool
          } catch { /* skip */ }
        }))
        setMarketMap(mMap)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <span style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>
        Loading events...
      </span>
    </div>
  )

  const poolEntries = eventList.filter(evt => marketMap[evt.id])

  return (
    <div>
      <div className="mb-6">
        <div className="text-base font-black mb-1">Pool Markets</div>
        <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          Select an event to add liquidity
        </div>
      </div>
      {poolEntries.length === 0 ? (
        <div className="text-center py-20 text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          No open Pool markets
        </div>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
          {poolEntries.map(evt => {
            const market = marketMap[evt.id]
            return (
              <div
                key={evt.id}
                onClick={() => navigate(`/pool?market=${market.id}`)}
                className="rounded-lg p-4 cursor-pointer transition-all"
                style={{ background: '#111820', border: '1px solid rgba(0,255,136,0.08)' }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'rgba(0,255,136,0.22)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'rgba(0,255,136,0.08)'
                  e.currentTarget.style.transform = 'none'
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded"
                    style={{ background: 'rgba(0,255,136,0.08)', color: '#00ff88', border: '1px solid rgba(0,255,136,0.15)', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}>
                    {evt.game_type}
                  </span>
                  <span className="text-xs font-bold px-2 py-0.5 rounded"
                    style={{ background: 'rgba(0,255,136,0.08)', color: '#00ff88', border: '1px solid rgba(0,255,136,0.15)', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}>
                    POOL
                  </span>
                </div>
                <div className="flex items-center justify-between my-3">
                  <span className="text-sm font-black">{evt.team_a}</span>
                  <span className="text-xs px-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>vs</span>
                  <span className="text-sm font-black">{evt.team_b}</span>
                </div>
                <div className="text-xs truncate" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
                  {evt.tournament}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── Pool Bar ─────────────────────────────────────────────────────────────────

function PoolBar({ poolState }: { poolState: PoolState }) {
  const total = parseFloat(poolState.total_pool) || 1
  return (
    <div>
      <div className="flex justify-between text-xs mb-1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
        <span style={{ color: '#e2e8f0' }}>Total Pool</span>
        <span style={{ color: '#00ff88' }}>{parseFloat(poolState.total_pool).toFixed(2)} CR</span>
      </div>

      {/* Bar */}
      <div className="h-3 rounded-full overflow-hidden flex mb-3" style={{ background: '#1a2535' }}>
        {poolState.outcomes.map((o, i) => {
          const pct = (parseFloat(o.total_staked) / total) * 100
          const colors = ['linear-gradient(90deg,#00d4ff,#0099bb)', 'linear-gradient(90deg,#7700cc,#aa33ff)', 'linear-gradient(90deg,#ff8800,#ffaa33)']
          return pct > 0 ? (
            <div key={o.outcome_id} className="h-full transition-all duration-700"
              style={{ width: `${pct}%`, background: colors[i % colors.length] }} />
          ) : null
        })}
      </div>

      {/* Outcome stats */}
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${poolState.outcomes.length}, 1fr)` }}>
        {poolState.outcomes.map((o, i) => {
          const pct = total > 1 ? ((parseFloat(o.total_staked) / total) * 100).toFixed(1) : '0.0'
          const dotColors = ['#00d4ff', '#aa33ff', '#ffaa33']
          return (
            <div key={o.outcome_id} className="rounded-lg p-3"
              style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.06)' }}>
              <div className="flex items-center gap-1.5 mb-2">
                <div className="w-2 h-2 rounded-full" style={{ background: dotColors[i % dotColors.length] }} />
                <span className="text-xs font-bold truncate">{o.outcome_name}</span>
              </div>
              <div className="text-xs" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                <div className="flex justify-between mb-1">
                  <span style={{ color: '#4a5568' }}>Staked</span>
                  <span style={{ color: '#e2e8f0' }}>{parseFloat(o.total_staked).toFixed(0)} CR</span>
                </div>
                <div className="flex justify-between mb-1">
                  <span style={{ color: '#4a5568' }}>Share</span>
                  <span style={{ color: '#e2e8f0' }}>{pct}%</span>
                </div>
                <div className="flex justify-between mb-1">
                  <span style={{ color: '#4a5568' }}>Est. odds</span>
                  <span style={{ color: '#00ff88' }}>×{parseFloat(o.estimated_odds).toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: '#4a5568' }}>Bettors</span>
                  <span style={{ color: '#e2e8f0' }}>{o.participant_count}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Bet Panel ────────────────────────────────────────────────────────────────

function BetPanel({ market, poolState, onSuccess }: {
  market: Market
  poolState: PoolState | null
  onSuccess: () => void
}) {
  const { user } = useAuthStore()
  const [selectedOutcome, setSelectedOutcome] = useState<Outcome | null>(market.outcomes[0] ?? null)
  const [amount, setAmount] = useState('100')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const stake = parseFloat(amount) || 0
  const balance = parseFloat(user?.balance_available ?? '0')

  // Calculate preview pool share
  const outcomeState = poolState?.outcomes.find(o => o.outcome_id === selectedOutcome?.id)
  const currentPool = parseFloat(outcomeState?.total_staked ?? '0')
  const totalPool = parseFloat(poolState?.total_pool ?? '0')
  const newOutcomePool = currentPool + stake
  const newTotalPool = totalPool + stake
  const myShare = newOutcomePool > 0 ? (stake / newOutcomePool) * 100 : 100
  const estimatedPayout = newTotalPool > 0 ? (stake / newOutcomePool) * newTotalPool : stake * 2
  const estimatedProfit = estimatedPayout - stake
  const estimatedFee = Math.max(0, estimatedProfit * 0.02)
  const estimatedNet = estimatedPayout - estimatedFee

  const handleBet = async () => {
    if (!selectedOutcome) return setError('Select an outcome')
    if (stake <= 0) return setError('Enter a valid amount')
    if (stake > balance) return setError('Insufficient balance')

    setLoading(true)
    setError('')
    try {
      await poolMarkets.bet(market.id, selectedOutcome.id, stake.toFixed(2))
      setSuccess('Bet placed!')
      setTimeout(() => { setSuccess(''); onSuccess() }, 1500)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to place bet')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    background: '#07090f',
    border: '1px solid rgba(0,255,136,0.08)',
    color: '#e2e8f0',
    fontFamily: 'JetBrains Mono, monospace',
  }
  const focusStyle = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = '#00ff88'
    e.target.style.boxShadow = '0 0 0 3px rgba(0,255,136,0.08)'
  }
  const blurStyle = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = 'rgba(0,255,136,0.08)'
    e.target.style.boxShadow = 'none'
  }

  return (
    <div className="rounded-lg p-4 flex flex-col gap-4"
      style={{ background: '#111820', border: '1px solid rgba(0,255,136,0.08)' }}>

      {/* Outcome select */}
      <div>
        <div className="text-xs uppercase tracking-widest mb-2"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          Bet on
        </div>
        <div className="flex gap-2">
          {market.outcomes.map((o) => (
            <button
              key={o.id}
              onClick={() => setSelectedOutcome(o)}
              className="flex-1 py-2 px-3 rounded-lg text-sm font-bold transition-all"
              style={{
                background: selectedOutcome?.id === o.id ? 'rgba(0,255,136,0.1)' : '#0d1117',
                border: `1px solid ${selectedOutcome?.id === o.id ? '#00ff88' : 'rgba(0,255,136,0.08)'}`,
                boxShadow: selectedOutcome?.id === o.id ? '0 0 12px rgba(0,255,136,0.12)' : 'none',
                color: selectedOutcome?.id === o.id ? '#00ff88' : '#4a5568',
              }}
            >
              {o.name}
            </button>
          ))}
        </div>
      </div>

      {/* Amount */}
      <div>
        <div className="text-xs uppercase tracking-widest mb-2"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          Stake
        </div>
        <div className="relative">
          <input
            className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all pr-10"
            style={inputStyle}
            type="number"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            onFocus={focusStyle}
            onBlur={blurStyle}
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>CR</span>
        </div>
      </div>

      {/* Preview */}
      <div className="rounded-lg p-3 flex flex-col gap-1.5"
        style={{ background: '#0d1117', border: '1px solid rgba(0,255,136,0.06)' }}>
        <div className="text-xs uppercase tracking-widest mb-1"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          Preview
        </div>
        {[
          ['Stake', `${stake.toFixed(2)} CR`, '#e2e8f0'],
          ['Pool share', `${myShare.toFixed(1)}%`, '#e2e8f0'],
          ['Est. odds', `×${newOutcomePool > 0 ? (newTotalPool / newOutcomePool).toFixed(2) : '2.00'}`, '#00ff88'],
          ['Fee (2%)', `${estimatedFee.toFixed(2)} CR`, '#4a5568'],
        ].map(([label, value, color]) => (
          <div key={label} className="flex justify-between text-xs" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
            <span style={{ color: '#4a5568' }}>{label}</span>
            <span style={{ color }}>{value}</span>
          </div>
        ))}
        <div className="flex justify-between text-sm font-bold pt-1.5 mt-1"
          style={{ borderTop: '1px solid rgba(0,255,136,0.08)', fontFamily: 'JetBrains Mono, monospace' }}>
          <span style={{ color: '#e2e8f0' }}>If you win</span>
          <span style={{ color: '#00ff88' }}>+{estimatedNet.toFixed(2)} CR</span>
        </div>
        <div className="text-xs mt-1" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          * Estimated. Final payout depends on total pool at settlement.
        </div>
      </div>

      {error && (
        <div className="text-xs px-3 py-2 rounded-lg"
          style={{ background: 'rgba(255,51,102,0.1)', color: '#ff3366', fontFamily: 'JetBrains Mono, monospace' }}>
          {error}
        </div>
      )}
      {success && (
        <div className="text-xs px-3 py-2 rounded-lg"
          style={{ background: 'rgba(0,255,136,0.1)', color: '#00ff88', fontFamily: 'JetBrains Mono, monospace' }}>
          {success}
        </div>
      )}

      <button
        onClick={handleBet}
        disabled={loading}
        className="w-full py-2.5 rounded-lg text-sm font-black tracking-wide transition-all"
        style={{
          background: loading ? 'rgba(0,255,136,0.4)' : '#00ff88',
          color: '#07090f',
          boxShadow: loading ? 'none' : '0 0 20px rgba(0,255,136,0.25)',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? 'Processing...' : 'Place Bet'}
      </button>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function PoolPage() {
  const [searchParams] = useSearchParams()
  const marketId = searchParams.get('market')

  const [market, setMarket] = useState<Market | null>(null)
  const [poolState, setPoolState] = useState<PoolState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadPoolState = async (id: number) => {
    try {
      const { data } = await poolMarkets.state(id)
      setPoolState(data)
    } catch { /* skip */ }
  }

  useEffect(() => {
    if (!marketId) { setLoading(false); return }
    const load = async () => {
      setLoading(true)
      try {
        const { data: mkt } = await markets.get(parseInt(marketId))
        setMarket(mkt)
        await loadPoolState(mkt.id)
      } catch {
        setError('Failed to load market')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [marketId])

  if (!marketId) return <EventSelector />

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <span style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>
        Loading pool...
      </span>
    </div>
  )

  if (error || !market) return (
    <div className="flex items-center justify-center py-20">
      <span style={{ color: '#ff3366', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>
        {error || 'Market not found.'}
      </span>
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded"
          style={{ background: 'rgba(0,255,136,0.08)', color: '#00ff88', border: '1px solid rgba(0,255,136,0.15)', fontFamily: 'JetBrains Mono, monospace' }}>
          Pool Market
        </div>
        <div>
          <div className="text-base font-black">{market.title}</div>
          <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Market #{market.id} · {market.status}
          </div>
        </div>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 320px' }}>
        {/* Pool visualization */}
        <div className="rounded-lg p-4" style={{ background: '#111820', border: '1px solid rgba(0,255,136,0.08)' }}>
          <div className="text-xs uppercase tracking-widest mb-4"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Liquidity Pool
          </div>
          {poolState ? (
            <PoolBar poolState={poolState} />
          ) : (
            <div className="text-center py-10 text-xs"
              style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
              No pool data available
            </div>
          )}
        </div>

        {/* Bet panel */}
        <BetPanel
          market={market}
          poolState={poolState}
          onSuccess={() => loadPoolState(market.id)}
        />
      </div>
    </div>
  )
}