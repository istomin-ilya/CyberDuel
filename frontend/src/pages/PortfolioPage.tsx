import { useEffect, useMemo, useState } from 'react'
import { contracts, markets, orders, portfolio } from '@/api/endpoints'
import { useAuthStore } from '@/store/authStore'
import type { ContractDetail, Market, Order, PoolBet, Transaction } from '@/types/api'

type TabKey = 'overview' | 'orders' | 'contracts' | 'pool' | 'transactions'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'orders', label: 'P2P Orders' },
  { key: 'contracts', label: 'Contracts' },
  { key: 'pool', label: 'Pool Bets' },
  { key: 'transactions', label: 'Transactions' },
]

const statusColor: Record<string, string> = {
  OPEN: '#00d4ff',
  PARTIALLY_FILLED: '#ffaa33',
  FILLED: '#00ff88',
  CANCELLED: '#4a5568',
  ACTIVE: '#00d4ff',
  CLAIMED: '#ffaa33',
  SETTLED: '#00ff88',
  DISPUTED: '#ff3366',
}

const txTypeColor: Record<string, string> = {
  DEPOSIT: '#00ff88',
  SETTLEMENT: '#00ff88',
  ORDER_LOCK: '#ffaa33',
  CONTRACT_LOCK: '#ffaa33',
  ORDER_UNLOCK: '#00d4ff',
  FEE: '#ff3366',
}

const cardStyle: React.CSSProperties = {
  background: '#111820',
  border: '1px solid rgba(0,212,255,0.08)',
}

function formatAmount(value: string | number | null | undefined) {
  const numberValue = Number(value ?? 0)
  return `${numberValue.toFixed(2)} CR`
}

function formatDate(iso?: string | null) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString()
}

function badgeStyle(color: string): React.CSSProperties {
  return {
    color,
    border: `1px solid ${color}55`,
    background: `${color}1A`,
    fontFamily: 'JetBrains Mono, monospace',
  }
}

export default function PortfolioPage() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  const [ordersList, setOrdersList] = useState<Order[]>([])
  const [contractsList, setContractsList] = useState<ContractDetail[]>([])
  const [poolBets, setPoolBets] = useState<PoolBet[]>([])
  const [transactions, setTransactions] = useState<Transaction[]>([])

  const [marketMap, setMarketMap] = useState<Record<number, Market>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [txPage, setTxPage] = useState(1)
  const [txTotal, setTxTotal] = useState(0)
  const txPageSize = 20

  const activeOrdersCount = useMemo(
    () => ordersList.filter((item) => item.status === 'OPEN' || item.status === 'PARTIALLY_FILLED').length,
    [ordersList],
  )

  const activeContractsCount = useMemo(
    () => contractsList.filter((item) => item.status === 'ACTIVE' || item.status === 'CLAIMED').length,
    [contractsList],
  )

  const activePoolBetsCount = useMemo(
    () => poolBets.filter((item) => !item.settled).length,
    [poolBets],
  )

  const totalBalance = useMemo(() => {
    const available = Number(user?.balance_available ?? '0')
    const locked = Number(user?.balance_locked ?? '0')
    return available + locked
  }, [user?.balance_available, user?.balance_locked])

  const ensureMarketMap = async (marketIds: number[]) => {
    const uniqueMissing = [...new Set(marketIds)].filter((id) => !marketMap[id])
    if (uniqueMissing.length === 0) return

    const results = await Promise.all(
      uniqueMissing.map(async (id) => {
        try {
          const { data } = await markets.get(id)
          return [id, data] as const
        } catch {
          return null
        }
      }),
    )

    const updates: Record<number, Market> = {}
    results.forEach((entry) => {
      if (!entry) return
      updates[entry[0]] = entry[1]
    })

    if (Object.keys(updates).length > 0) {
      setMarketMap((prev) => ({ ...prev, ...updates }))
    }
  }

  const loadOverview = async () => {
    const [myOrdersRes, myContractsRes, myPoolRes, txRes] = await Promise.all([
      portfolio.getMyOrders(),
      portfolio.getMyContracts(),
      portfolio.getMyPoolBets({ page: 1, page_size: 100 }),
      portfolio.getMyTransactions(1, 5),
    ])

    setOrdersList(myOrdersRes.data.orders)
    setContractsList(myContractsRes.data.contracts)
    setPoolBets(myPoolRes.data.bets)
    setTransactions(txRes.data.transactions)

    await ensureMarketMap([
      ...myOrdersRes.data.orders.map((item) => item.market_id),
      ...myContractsRes.data.contracts.map((item) => item.market_id),
      ...myPoolRes.data.bets.map((item) => item.market_id),
    ])
  }

  const loadOrders = async () => {
    const { data } = await portfolio.getMyOrders()
    setOrdersList(data.orders)
    await ensureMarketMap(data.orders.map((item) => item.market_id))
  }

  const loadContracts = async () => {
    const { data } = await portfolio.getMyContracts()
    setContractsList(data.contracts)
    await ensureMarketMap(data.contracts.map((item) => item.market_id))
  }

  const loadPoolBets = async () => {
    const { data } = await portfolio.getMyPoolBets({ page: 1, page_size: 100 })
    setPoolBets(data.bets)
    await ensureMarketMap(data.bets.map((item) => item.market_id))
  }

  const loadTransactions = async (page = txPage) => {
    const { data } = await portfolio.getMyTransactions(page, txPageSize)
    setTransactions(data.transactions)
    setTxTotal(data.total)
  }

  const loadForTab = async (tab: TabKey) => {
    setLoading(true)
    setError('')
    try {
      if (tab === 'overview') await loadOverview()
      if (tab === 'orders') await loadOrders()
      if (tab === 'contracts') await loadContracts()
      if (tab === 'pool') await loadPoolBets()
      if (tab === 'transactions') await loadTransactions(tab === 'transactions' ? txPage : 1)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to load portfolio data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadForTab(activeTab)
  }, [activeTab])

  useEffect(() => {
    if (activeTab !== 'transactions') return
    loadForTab('transactions')
  }, [txPage])

  const marketTitle = (marketId: number) => marketMap[marketId]?.title ?? `Market #${marketId}`
  const outcomeName = (marketId: number, outcomeId: number) => {
    const outcome = marketMap[marketId]?.outcomes.find((item) => item.id === outcomeId)
    return outcome?.name ?? `Outcome #${outcomeId}`
  }

  const onCancelOrder = async (orderId: number) => {
    try {
      await orders.cancel(orderId)
      await loadOrders()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to cancel order')
    }
  }

  const onClaimContract = async (contract: ContractDetail, winningOutcomeId: number) => {
    try {
      await contracts.claim(contract.id, winningOutcomeId)
      await loadContracts()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to claim contract')
    }
  }

  const onDisputeContract = async (contractId: number) => {
    try {
      await contracts.dispute(contractId)
      await loadContracts()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to dispute claim')
    }
  }

  const tabButton = (tab: TabKey, label: string) => (
    <button
      key={tab}
      onClick={() => setActiveTab(tab)}
      className="px-3 py-1.5 rounded-md text-xs font-bold transition-all"
      style={{
        background: activeTab === tab ? 'rgba(0,212,255,0.1)' : 'transparent',
        color: activeTab === tab ? '#00d4ff' : '#4a5568',
        fontFamily: 'JetBrains Mono, monospace',
      }}
    >
      {label}
    </button>
  )

  return (
    <div>
      <div className="flex gap-1 p-1 rounded-lg mb-6" style={{ background: '#0d1117', border: '1px solid rgba(0,212,255,0.08)' }}>
        {TABS.map((tab) => tabButton(tab.key, tab.label))}
      </div>

      {error ? (
        <div className="mb-4 text-xs px-3 py-2 rounded-lg" style={{ background: 'rgba(255,51,102,0.1)', color: '#ff3366', fontFamily: 'JetBrains Mono, monospace' }}>
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="text-xs tracking-widest" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Loading portfolio data...
          </div>
        </div>
      ) : null}

      {!loading && activeTab === 'overview' ? (
        <div className="flex flex-col gap-4">
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <div className="rounded-lg p-4" style={cardStyle}>
              <div className="text-xs uppercase tracking-widest mb-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>Available</div>
              <div className="text-xl font-black" style={{ color: '#00ff88' }}>{formatAmount(user?.balance_available)}</div>
            </div>
            <div className="rounded-lg p-4" style={cardStyle}>
              <div className="text-xs uppercase tracking-widest mb-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>Locked</div>
              <div className="text-xl font-black" style={{ color: '#00d4ff' }}>{formatAmount(user?.balance_locked)}</div>
            </div>
            <div className="rounded-lg p-4" style={cardStyle}>
              <div className="text-xs uppercase tracking-widest mb-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>Total</div>
              <div className="text-xl font-black" style={{ color: '#e2e8f0' }}>{formatAmount(totalBalance)}</div>
            </div>
          </div>

          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <div className="rounded-lg p-4" style={cardStyle}>
              <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>Active Orders</div>
              <div className="text-2xl font-black" style={{ color: '#00d4ff' }}>{activeOrdersCount}</div>
            </div>
            <div className="rounded-lg p-4" style={cardStyle}>
              <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>Active Contracts</div>
              <div className="text-2xl font-black" style={{ color: '#00d4ff' }}>{activeContractsCount}</div>
            </div>
            <div className="rounded-lg p-4" style={cardStyle}>
              <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>Active Pool Bets</div>
              <div className="text-2xl font-black" style={{ color: '#00d4ff' }}>{activePoolBetsCount}</div>
            </div>
          </div>

          <div className="rounded-lg p-4" style={cardStyle}>
            <div className="text-sm font-black mb-3">Recent Transactions</div>
            {transactions.length === 0 ? (
              <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>No transactions yet</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}>
                      <th className="text-left py-2">Type</th>
                      <th className="text-left py-2">Amount</th>
                      <th className="text-left py-2">Description</th>
                      <th className="text-left py-2">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((item) => (
                      <tr key={item.id} style={{ borderTop: '1px solid rgba(0,212,255,0.08)' }}>
                        <td className="py-2">
                          <span className="px-2 py-0.5 rounded text-xs font-bold" style={badgeStyle(txTypeColor[item.type] ?? '#4a5568')}>
                            {item.type}
                          </span>
                        </td>
                        <td className="py-2">{formatAmount(item.amount)}</td>
                        <td className="py-2">{item.description ?? '—'}</td>
                        <td className="py-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>{formatDate(item.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {!loading && activeTab === 'orders' ? (
        <div className="rounded-lg p-4 overflow-x-auto" style={cardStyle}>
          {ordersList.length === 0 ? (
            <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>No P2P orders found</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}>
                  <th className="text-left py-2">Market</th>
                  <th className="text-left py-2">Outcome</th>
                  <th className="text-left py-2">Amount</th>
                  <th className="text-left py-2">Odds</th>
                  <th className="text-left py-2">Filled</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Created</th>
                  <th className="text-left py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {ordersList.map((item) => {
                  const filled = Number(item.amount) - Number(item.unfilled_amount)
                  const canCancel = item.status === 'OPEN' || item.status === 'PARTIALLY_FILLED'
                  return (
                    <tr key={item.id} style={{ borderTop: '1px solid rgba(0,212,255,0.08)' }}>
                      <td className="py-2">{marketTitle(item.market_id)}</td>
                      <td className="py-2">{outcomeName(item.market_id, item.outcome_id)}</td>
                      <td className="py-2">{formatAmount(item.amount)}</td>
                      <td className="py-2">×{Number(item.odds).toFixed(2)}</td>
                      <td className="py-2">{formatAmount(filled)}</td>
                      <td className="py-2">
                        <span className="px-2 py-0.5 rounded text-xs font-bold" style={badgeStyle(statusColor[item.status] ?? '#4a5568')}>
                          {item.status}
                        </span>
                      </td>
                      <td className="py-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>{formatDate(item.created_at)}</td>
                      <td className="py-2">
                        {canCancel ? (
                          <button
                            onClick={() => onCancelOrder(item.id)}
                            className="px-2 py-1 rounded text-xs font-bold"
                            style={{ background: 'rgba(255,51,102,0.1)', color: '#ff3366', border: '1px solid rgba(255,51,102,0.2)' }}
                          >
                            Cancel
                          </button>
                        ) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      ) : null}

      {!loading && activeTab === 'contracts' ? (
        <div className="rounded-lg p-4 overflow-x-auto" style={cardStyle}>
          {contractsList.length === 0 ? (
            <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>No contracts found</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}>
                  <th className="text-left py-2">Market</th>
                  <th className="text-left py-2">Role</th>
                  <th className="text-left py-2">Amount</th>
                  <th className="text-left py-2">Odds</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {contractsList.map((item) => {
                  const isMaker = item.maker_id === user?.id
                  const isClaimable = item.status === 'ACTIVE'
                  const canDispute = item.status === 'CLAIMED' && item.claim_initiated_by !== user?.id
                  const market = marketMap[item.market_id]
                  return (
                    <tr key={item.id} style={{ borderTop: '1px solid rgba(0,212,255,0.08)' }}>
                      <td className="py-2">{marketTitle(item.market_id)}</td>
                      <td className="py-2">
                        <span className="px-2 py-0.5 rounded text-xs font-bold" style={badgeStyle(isMaker ? '#00d4ff' : '#00ff88')}>
                          {isMaker ? 'MAKER' : 'TAKER'}
                        </span>
                      </td>
                      <td className="py-2">{formatAmount(item.amount)}</td>
                      <td className="py-2">×{Number(item.odds).toFixed(2)}</td>
                      <td className="py-2">
                        <span className="px-2 py-0.5 rounded text-xs font-bold" style={badgeStyle(statusColor[item.status] ?? '#4a5568')}>
                          {item.status}
                        </span>
                      </td>
                      <td className="py-2">
                        {isClaimable ? (
                          <div className="flex flex-wrap gap-1">
                            {(market?.outcomes ?? []).map((outcome) => (
                              <button
                                key={outcome.id}
                                onClick={() => onClaimContract(item, outcome.id)}
                                className="px-2 py-1 rounded text-xs font-bold"
                                style={{ background: 'rgba(0,212,255,0.1)', color: '#00d4ff', border: '1px solid rgba(0,212,255,0.2)' }}
                              >
                                Claim {outcome.name}
                              </button>
                            ))}
                          </div>
                        ) : canDispute ? (
                          <button
                            onClick={() => onDisputeContract(item.id)}
                            className="px-2 py-1 rounded text-xs font-bold"
                            style={{ background: 'rgba(255,51,102,0.1)', color: '#ff3366', border: '1px solid rgba(255,51,102,0.2)' }}
                          >
                            Dispute
                          </button>
                        ) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      ) : null}

      {!loading && activeTab === 'pool' ? (
        <div className="rounded-lg p-4 overflow-x-auto" style={cardStyle}>
          {poolBets.length === 0 ? (
            <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>No pool bets found</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}>
                  <th className="text-left py-2">Market</th>
                  <th className="text-left py-2">Outcome</th>
                  <th className="text-left py-2">Amount</th>
                  <th className="text-left py-2">Pool Share %</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Payout</th>
                  <th className="text-left py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {poolBets.map((item) => (
                  <tr key={item.id} style={{ borderTop: '1px solid rgba(0,212,255,0.08)' }}>
                    <td className="py-2">{marketTitle(item.market_id)}</td>
                    <td className="py-2">{outcomeName(item.market_id, item.outcome_id)}</td>
                    <td className="py-2">{formatAmount(item.amount)}</td>
                    <td className="py-2">{Number(item.initial_pool_share_percentage).toFixed(2)}%</td>
                    <td className="py-2">
                      <span className="px-2 py-0.5 rounded text-xs font-bold" style={badgeStyle(item.settled ? '#00ff88' : '#00d4ff')}>
                        {item.settled ? 'SETTLED' : 'ACTIVE'}
                      </span>
                    </td>
                    <td className="py-2">{item.settled ? formatAmount(item.actual_payout) : '—'}</td>
                    <td className="py-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}

      {!loading && activeTab === 'transactions' ? (
        <div className="rounded-lg p-4" style={cardStyle}>
          {transactions.length === 0 ? (
            <div className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>No transactions found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px' }}>
                    <th className="text-left py-2">Type</th>
                    <th className="text-left py-2">Amount</th>
                    <th className="text-left py-2">Description</th>
                    <th className="text-left py-2">Balance After</th>
                    <th className="text-left py-2">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((item) => (
                    <tr key={item.id} style={{ borderTop: '1px solid rgba(0,212,255,0.08)' }}>
                      <td className="py-2">
                        <span className="px-2 py-0.5 rounded text-xs font-bold" style={badgeStyle(txTypeColor[item.type] ?? '#4a5568')}>
                          {item.type}
                        </span>
                      </td>
                      <td className="py-2">{formatAmount(item.amount)}</td>
                      <td className="py-2">{item.description ?? '—'}</td>
                      <td className="py-2">{formatAmount(item.balance_available_after)}</td>
                      <td className="py-2" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>{formatDate(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 mt-4">
            <button
              onClick={() => setTxPage((prev) => Math.max(1, prev - 1))}
              disabled={txPage <= 1}
              className="px-3 py-1.5 rounded text-xs font-bold"
              style={{
                background: txPage <= 1 ? 'rgba(74,85,104,0.2)' : 'rgba(0,212,255,0.1)',
                color: txPage <= 1 ? '#4a5568' : '#00d4ff',
                border: '1px solid rgba(0,212,255,0.15)',
              }}
            >
              Prev
            </button>
            <span className="text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
              Page {txPage}
            </span>
            <button
              onClick={() => setTxPage((prev) => prev + 1)}
              disabled={txPage * txPageSize >= txTotal}
              className="px-3 py-1.5 rounded text-xs font-bold"
              style={{
                background: txPage * txPageSize >= txTotal ? 'rgba(74,85,104,0.2)' : 'rgba(0,212,255,0.1)',
                color: txPage * txPageSize >= txTotal ? '#4a5568' : '#00d4ff',
                border: '1px solid rgba(0,212,255,0.15)',
              }}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
