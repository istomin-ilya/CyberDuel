export interface User {
  id: number
  email: string
  balance_available: string
  balance_locked: string
  is_admin: boolean
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface Event {
  id: number
  game_type: string
  team_a: string
  team_b: string
  tournament: string
  status: 'SCHEDULED' | 'OPEN' | 'LIVE' | 'FINISHED' | 'SETTLED'
  scheduled_start: string
  external_match_id: string | null
}

export interface Outcome {
  id: number
  name: string
}

export interface Market {
  id: number
  event_id: number
  market_type: string
  title: string
  status: 'PENDING' | 'OPEN' | 'LOCKED' | 'SETTLED'
  market_mode: 'p2p_direct' | 'pool_market'
  winning_outcome_id: number | null
  outcomes: Outcome[]
}

export interface Order {
  id: number
  user_id: number
  market_id: number
  outcome_id: number
  amount: string
  unfilled_amount: string
  odds: string
  status: 'OPEN' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED'
  created_at: string
}

export interface Contract {
  id: number
  market_id: number
  order_id: number
  maker_id: number
  taker_id: number
  outcome_id: number
  amount: string
  odds: string
  status: 'ACTIVE' | 'CLAIMED' | 'SETTLED' | 'DISPUTED'
  winner_id: number | null
  settled_at: string | null
}

export interface ContractDetail extends Contract {
  claim_initiated_by?: number | null
  claim_initiated_at?: string | null
  challenge_deadline?: string | null
  disputed_by?: number | null
  disputed_at?: string | null
  created_at: string
}

export interface PoolBet {
  id: number
  user_id: number
  market_id: number
  outcome_id: number
  amount: string
  initial_pool_share_percentage: string
  pool_size_at_bet: string
  settled: boolean
  actual_payout: string | null
  created_at?: string
}

export interface PoolState {
  market_id: number
  total_pool: string
  outcomes: {
    outcome_id: number
    outcome_name: string
    total_staked: string
    participant_count: number
    estimated_odds: string
    estimated_roi: string
  }[]
}

export interface Transaction {
  id: number
  type:
    | 'DEPOSIT'
    | 'WITHDRAWAL'
    | 'ORDER_LOCK'
    | 'ORDER_UNLOCK'
    | 'CONTRACT_LOCK'
    | 'POOL_BET_LOCK'
    | 'SETTLEMENT'
    | 'FEE'
    | string
  amount: string
  description: string | null
  balance_available_before: string
  balance_available_after: string
  balance_locked_before: string
  balance_locked_after: string
  order_id: number | null
  contract_id: number | null
  created_at: string
}

export interface MyContractsResponse {
  contracts: ContractDetail[]
  total: number
}

export interface TransactionListResponse {
  transactions: Transaction[]
  total: number
  page: number
  page_size: number
}