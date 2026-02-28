import client from '@/api/client'
import type { AuthResponse, User, Event, Market, Order, Contract, PoolBet, PoolState } from '@/types/api'

// ─── AUTH ───
export const auth = {
  register: (email: string, password: string) =>
    client.post<AuthResponse>('/auth/register', { email, password }),

  login: (email: string, password: string) =>
    client.post<AuthResponse>('/auth/login', { email, password }),

  me: () =>
    client.get<User>('/auth/me'),
}

// ─── EVENTS ───
export const events = {
  list: (params?: { status?: string; game_type?: string; skip?: number; limit?: number }) =>
    client.get<{ events: Event[]; total: number }>('/api/events', { params }),

  get: (id: number) =>
    client.get<Event>(`/api/events/${id}`),
}

// ─── MARKETS ───
export const markets = {
  list: (params?: { event_id?: number; status?: string; skip?: number; limit?: number }) =>
    client.get<{ markets: Market[]; total: number }>('/api/markets', { params }),

  get: (id: number) =>
    client.get<Market>(`/api/markets/${id}`),
}

// ─── ORDERS (P2P) ───
export const orders = {
  list: (params?: { market_id?: number; outcome_id?: number; status?: string; skip?: number; limit?: number }) =>
    client.get<{ orders: Order[]; total: number }>('/api/orders', { params }),

  get: (id: number) =>
    client.get<Order>(`/api/orders/${id}`),

  create: (data: { market_id: number; outcome_id: number; amount: string; odds: string }) =>
    client.post<Order>('/api/orders', data),

  cancel: (id: number) =>
    client.delete(`/api/orders/${id}`),

  match: (id: number, amount: string) =>
    client.post<Contract>(`/api/orders/${id}/match`, { amount }),
}

// ─── CONTRACTS ───
export const contracts = {
  get: (id: number) =>
    client.get<Contract>(`/api/settlement/contracts/${id}`),

  claim: (id: number, winning_outcome_id: number) =>
    client.post(`/api/settlement/contracts/${id}/claim`, { winning_outcome_id }),

  dispute: (id: number, reason?: string) =>
    client.post(`/api/settlement/contracts/${id}/dispute`, { reason }),

  pendingClaims: () =>
    client.get<Contract[]>(`/api/settlement/contracts/pending-claims`),
}

// ─── POOL MARKETS ───
export const poolMarkets = {
  state: (id: number) =>
    client.get<PoolState>(`/api/pool-markets/${id}/state`),

  bet: (id: number, outcome_id: number, amount: string) =>
    client.post<PoolBet>(`/api/pool-markets/${id}/bet`, { outcome_id, amount }),

  myBets: (id: number, params?: { settled?: boolean; page?: number; page_size?: number }) =>
    client.get<{ bets: PoolBet[]; total: number; page: number; page_size: number }>(`/api/pool-markets/${id}/my-bets`, { params }),

  allBets: (id: number, params?: { settled?: boolean; page?: number; page_size?: number }) =>
    client.get<{ bets: PoolBet[]; total: number; page: number; page_size: number }>(`/api/pool-markets/${id}/all-bets`, { params }),
}

// ─── ADMIN ───
export const admin = {
  disputes: (params?: { skip?: number; limit?: number }) =>
    client.get<{ contracts: Contract[]; total: number }>('/api/admin/disputes', { params }),

  resolveDispute: (contract_id: number, winning_outcome_id: number, resolution_notes?: string) =>
    client.post(`/api/admin/disputes/${contract_id}/resolve`, { winning_outcome_id, resolution_notes }),

  settleMarket: (market_id: number) =>
    client.post(`/api/admin/markets/${market_id}/settle`),

  makeAdmin: (user_id: number) =>
    client.post(`/api/admin/users/${user_id}/make-admin`),

  removeAdmin: (user_id: number) =>
    client.delete(`/api/admin/users/${user_id}/remove-admin`),
}