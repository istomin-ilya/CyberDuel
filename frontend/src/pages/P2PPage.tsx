import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { events, markets, orders } from '@/api/endpoints'
import { useAuthStore } from '@/store/authStore'
import type { Market, Order, Outcome } from '@/types/api'

// ─── helpers ────────────────────────────────────────────────────────────────

function calcTakerRisk(makerAmount: number, odds: number) {
  return makerAmount * (odds - 1)
}

function calcPayout(stake: number, odds: number) {
  const profit = stake * (odds - 1)
  const fee = profit * 0.02
  return stake + profit - fee
}

// ─── Order Row ───────────────────────────────────────────────────────────────

function OrderRow({ order, maxAmount, onMatch }: {
  order: Order
  maxAmount: number
  onMatch: (order: Order) => void
}) {
  const [hovered, setHovered] = useState(false)
  const fillPct = maxAmount > 0 ? (parseFloat(order.unfilled_amount) / maxAmount) * 100 : 20

  return (
    <div
      className="relative flex items-center px-3 py-2 rounded-md cursor-pointer overflow-hidden"
      style={{ transition: 'background 0.15s' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onMatch(order)}
    >
      {/* fill bar */}
      <div
        className="absolute left-0 top-0 bottom-0 rounded-md"
        style={{
          width: `${fillPct}%`,
          background: 'rgba(0,212,255,0.07)',
          transition: 'width 0.3s',
        }}
      />
      {hovered && (
        <div className="absolute inset-0 rounded-md" style={{ background: 'rgba(0,212,255,0.04)' }} />
      )}

      <span
        className="relative flex-1 font-bold"
        style={{ color: '#00d4ff', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}
      >
        ×{parseFloat(order.odds).toFixed(2)}
      </span>
      <span
        className="relative flex-1 text-center"
        style={{ color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}
      >
        {parseFloat(order.unfilled_amount).toFixed(2)}
      </span>
      <span
        className="relative flex-1 text-right"
        style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}
      >
        {(parseFloat(order.unfilled_amount) * parseFloat(order.odds)).toFixed(2)}
      </span>
    </div>
  )
}

// ─── Bet Panel ────────────────────────────────────────────────────────────────

function BetPanel({ market, selectedOutcome, onSuccess }: {
  market: Market
  selectedOutcome: Outcome | null
  onSuccess: () => void
}) {
  const { user } = useAuthStore()
  const [mode, setMode] = useState<'create' | 'match'>('create')
  const [amount, setAmount] = useState('100')
  const [oddsInput, setOddsInput] = useState('1.80')
  const [matchOrderId, setMatchOrderId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const stake = parseFloat(amount) || 0
  const odds = parseFloat(oddsInput) || 1.80
  const risk = calcTakerRisk(stake, odds)
  const fee = risk * 0.02
  const payout = calcPayout(stake, odds)
  const balance = parseFloat(user?.balance_available ?? '0')

  const handleCreate = async () => {
    if (!selectedOutcome) return setError('Select an outcome')
    if (stake <= 0) return setError('Enter a valid amount')
    if (odds < 1.01) return setError('Odds must be at least 1.01')
    if (stake > balance) return setError('Insufficient balance')

    setLoading(true)
    setError('')
    try {
      await orders.create({
        market_id: market.id,
        outcome_id: selectedOutcome.id,
        amount: stake.toFixed(2),
        odds: odds.toFixed(2),
      })
      setSuccess('Order created!')
      setTimeout(() => { setSuccess(''); onSuccess() }, 1500)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to create order')
    } finally {
      setLoading(false)
    }
  }

  const handleMatch = async () => {
    if (!matchOrderId) return setError('Enter order ID')
    if (stake <= 0) return setError('Enter a valid amount')

    setLoading(true)
    setError('')
    try {
      await orders.match(parseInt(matchOrderId), stake.toFixed(2))
      setSuccess('Order matched!')
      setTimeout(() => { setSuccess(''); onSuccess() }, 1500)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to match order')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    background: '#07090f',
    border: '1px solid rgba(0,212,255,0.08)',
    color: '#e2e8f0',
    fontFamily: 'JetBrains Mono, monospace',
  }

  const focusStyle = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = '#00d4ff'
    e.target.style.boxShadow = '0 0 0 3px rgba(0,212,255,0.08)'
  }
  const blurStyle = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = 'rgba(0,212,255,0.08)'
    e.target.style.boxShadow = 'none'
  }

  return (
    <div
      className="rounded-lg p-4 flex flex-col gap-4"
      style={{ background: '#111820', border: '1px solid rgba(0,212,255,0.08)' }}
    >
      {/* Mode tabs */}
      <div
        className="flex gap-1 p-1 rounded-lg"
        style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.08)' }}
      >
        {(['create', 'match'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className="flex-1 py-1.5 rounded-md text-xs font-bold transition-all"
            style={{
              background: mode === m ? 'rgba(0,212,255,0.1)' : 'transparent',
              color: mode === m ? '#00d4ff' : '#4a5568',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            {m === 'create' ? 'Create Order' : 'Match Order'}
          </button>
        ))}
      </div>

      {/* Selected outcome */}
      <div>
        <div
          className="text-xs uppercase tracking-widest mb-2"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
        >
          Outcome
        </div>
        <div className="flex gap-2">
          {market.outcomes.map((o) => (
            <div
              key={o.id}
              className="flex-1 py-2 px-3 rounded-lg text-center text-sm font-bold"
              style={{
                background: selectedOutcome?.id === o.id ? 'rgba(0,212,255,0.1)' : '#0d1117',
                border: `1px solid ${selectedOutcome?.id === o.id ? '#00d4ff' : 'rgba(0,212,255,0.08)'}`,
                boxShadow: selectedOutcome?.id === o.id ? '0 0 12px rgba(0,212,255,0.15)' : 'none',
                color: selectedOutcome?.id === o.id ? '#00d4ff' : '#4a5568',
              }}
            >
              {o.name}
            </div>
          ))}
        </div>
        <div
          className="text-xs mt-1"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
        >
          ← Select from order book
        </div>
      </div>

      {/* Match order ID (match mode only) */}
      {mode === 'match' && (
        <div>
          <div className="text-xs uppercase tracking-widest mb-2"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Order ID
          </div>
          <input
            className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
            style={inputStyle}
            placeholder="e.g. 42"
            value={matchOrderId}
            onChange={(e) => setMatchOrderId(e.target.value)}
            onFocus={focusStyle}
            onBlur={blurStyle}
          />
        </div>
      )}

      {/* Amount */}
      <div>
        <div className="text-xs uppercase tracking-widest mb-2"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          {mode === 'create' ? 'Your Stake' : 'Amount to Match'}
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
          <span
            className="absolute right-3 top-1/2 -translate-y-1/2 text-xs"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
          >
            CR
          </span>
        </div>
      </div>

      {/* Odds (create mode only) */}
      {mode === 'create' && (
        <div>
          <div className="text-xs uppercase tracking-widest mb-2"
            style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Odds
          </div>
          <div className="relative">
            <input
              className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all pr-10"
              style={inputStyle}
              type="number"
              step="0.05"
              min="1.01"
              value={oddsInput}
              onChange={(e) => setOddsInput(e.target.value)}
              onFocus={focusStyle}
              onBlur={blurStyle}
            />
            <span
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs"
              style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
            >
              ×
            </span>
          </div>
        </div>
      )}

      {/* Payout preview */}
      <div
        className="rounded-lg p-3 flex flex-col gap-1.5"
        style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.06)' }}
      >
        <div className="flex justify-between text-xs" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
          <span style={{ color: '#4a5568' }}>Stake</span>
          <span style={{ color: '#e2e8f0' }}>{stake.toFixed(2)} CR</span>
        </div>
        {mode === 'create' && (
          <>
            <div className="flex justify-between text-xs" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              <span style={{ color: '#4a5568' }}>Counterparty risk</span>
              <span style={{ color: '#e2e8f0' }}>{risk.toFixed(2)} CR</span>
            </div>
            <div className="flex justify-between text-xs" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              <span style={{ color: '#4a5568' }}>Fee (2%)</span>
              <span style={{ color: '#4a5568' }}>{fee.toFixed(2)} CR</span>
            </div>
            <div
              className="flex justify-between text-sm font-bold pt-1.5 mt-1"
              style={{ borderTop: '1px solid rgba(0,212,255,0.08)', fontFamily: 'JetBrains Mono, monospace' }}
            >
              <span style={{ color: '#e2e8f0' }}>If you win</span>
              <span style={{ color: '#00ff88' }}>+{payout.toFixed(2)} CR</span>
            </div>
          </>
        )}
      </div>

      {/* Error / Success */}
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

      {/* Submit */}
      <button
        onClick={mode === 'create' ? handleCreate : handleMatch}
        disabled={loading}
        className="w-full py-2.5 rounded-lg text-sm font-black tracking-wide transition-all"
        style={{
          background: loading ? 'rgba(0,212,255,0.4)' : '#00d4ff',
          color: '#07090f',
          boxShadow: loading ? 'none' : '0 0 20px rgba(0,212,255,0.3)',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? 'Processing...' : mode === 'create' ? 'Create Order' : 'Match Order'}
      </button>
    </div>
  )
}

// ─── Event Selector (when no market selected) ────────────────────────────────

function EventSelector() {
  const navigate = useNavigate()
  const [eventList, setEventList] = useState<any[]>([])
  const [marketMap, setMarketMap] = useState<Record<number, any>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await events.list({ status: 'OPEN' })
        const p2pEvents = data.events
        setEventList(p2pEvents)
        const mMap: Record<number, any> = {}
        await Promise.all(p2pEvents.map(async (evt: any) => {
          try {
            const { data: mks } = await markets.list({ event_id: evt.id })
            const p2p = mks.markets.find((m: any) => m.market_mode === 'p2p_direct')
            if (p2p) mMap[evt.id] = p2p
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

  const p2pEntries = eventList.filter(evt => marketMap[evt.id])

  return (
    <div>
      <div className="mb-6">
        <div className="text-base font-black mb-1">P2P Direct Markets</div>
        <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          Select an event to start trading
        </div>
      </div>
      {p2pEntries.length === 0 ? (
        <div className="text-center py-20 text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          No open P2P markets
        </div>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
          {p2pEntries.map(evt => {
            const market = marketMap[evt.id]
            return (
              <div
                key={evt.id}
                onClick={() => navigate(`/p2p?market=${market.id}`)}
                className="rounded-lg p-4 cursor-pointer transition-all"
                style={{ background: '#111820', border: '1px solid rgba(0,212,255,0.08)' }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'rgba(0,212,255,0.22)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'rgba(0,212,255,0.08)'
                  e.currentTarget.style.transform = 'none'
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded"
                    style={{ background: 'rgba(0,212,255,0.08)', color: '#00d4ff', border: '1px solid rgba(0,212,255,0.15)', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}>
                    {evt.game_type}
                  </span>
                  <span className="text-xs font-bold px-2 py-0.5 rounded"
                    style={{ background: 'rgba(0,212,255,0.08)', color: '#00d4ff', border: '1px solid rgba(0,212,255,0.15)', fontFamily: 'JetBrains Mono, monospace', fontSize: '9px' }}>
                    P2P
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

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function P2PPage() {
  const [searchParams] = useSearchParams()
  const marketId = searchParams.get('market')

  const [market, setMarket] = useState<Market | null>(null)
  const [orderList, setOrderList] = useState<Order[]>([])
  const [selectedOutcome, setSelectedOutcome] = useState<Outcome | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadOrders = async (mkt: Market, outcome: Outcome | null) => {
    if (!outcome) return
    try {
      const { data } = await orders.list({
        market_id: mkt.id,
        outcome_id: outcome.id,
        status: 'OPEN',
        my_orders: false,
      })
      setOrderList(data.orders ?? [])
    } catch {
      setOrderList([])
    }
  }

  useEffect(() => {
    if (!marketId) { setLoading(false); return }
    const load = async () => {
      setLoading(true)
      try {
        const { data: mkt } = await markets.get(parseInt(marketId))
        setMarket(mkt)
        const first = mkt.outcomes[0] ?? null
        setSelectedOutcome(first)
        await loadOrders(mkt, first)
      } catch {
        setError('Failed to load market')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [marketId])

  const handleOutcomeChange = async (outcome: Outcome) => {
    setSelectedOutcome(outcome)
    if (market) await loadOrders(market, outcome)
  }

  const maxAmount = Math.max(...orderList.map((o) => parseFloat(o.unfilled_amount)), 1)

  // ── No market selected → show event selector ──
  if (!marketId) return <EventSelector />

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <span style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>
        Loading market...
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
      <div className="flex items-center gap-3 mb-6">
        <div className="text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded"
          style={{ background: 'rgba(0,212,255,0.08)', color: '#00d4ff', border: '1px solid rgba(0,212,255,0.15)', fontFamily: 'JetBrains Mono, monospace' }}>
          P2P Direct
        </div>
        <div>
          <div className="text-base font-black">{market.title}</div>
          <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Market #{market.id} · {market.status}
          </div>
        </div>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 320px' }}>
        <div className="rounded-lg p-4" style={{ background: '#111820', border: '1px solid rgba(0,212,255,0.08)' }}>
          <div className="flex gap-1 p-1 rounded-lg mb-4 w-fit"
            style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.08)' }}>
            {market.outcomes.map((o) => (
              <button key={o.id} onClick={() => handleOutcomeChange(o)}
                className="px-4 py-1.5 rounded-md text-xs font-bold transition-all"
                style={{
                  background: selectedOutcome?.id === o.id ? 'rgba(0,212,255,0.1)' : 'transparent',
                  color: selectedOutcome?.id === o.id ? '#00d4ff' : '#4a5568',
                  fontFamily: 'JetBrains Mono, monospace',
                }}>
                {o.name}
              </button>
            ))}
          </div>

          <div className="grid px-3 pb-2 mb-1"
            style={{ gridTemplateColumns: '1fr 1fr 1fr', borderBottom: '1px solid rgba(0,212,255,0.06)' }}>
            {['Odds', 'Amount (CR)', 'Total'].map((h) => (
              <span key={h} className="text-xs uppercase tracking-widest last:text-right"
                style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>{h}</span>
            ))}
          </div>

          {orderList.length === 0 ? (
            <div className="text-center py-10 text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
              No open orders for this outcome
            </div>
          ) : (
            <div className="flex flex-col gap-0.5">
              {orderList.map((order) => (
                <OrderRow key={order.id} order={order} maxAmount={maxAmount}
                  onMatch={(o) => {
                    const outcome = market.outcomes.find(out => out.id === o.outcome_id)
                    if (outcome) setSelectedOutcome(outcome)
                  }} />
              ))}
            </div>
          )}
        </div>

        <BetPanel market={market} selectedOutcome={selectedOutcome}
          onSuccess={() => market && loadOrders(market, selectedOutcome)} />
      </div>
    </div>
  )
}