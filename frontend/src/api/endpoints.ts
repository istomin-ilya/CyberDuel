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
    client.get<Event[]>('/api/events', { params }),

  get: (id: number) =>
    client.get<Event>(`/api/events/${id}`),
}

// ─── MARKETS ───
export const markets = {
  list: (params?: { event_id?: number; status?: string }) =>
    client.get<Market[]>('/api/markets', { params }),

  get: (id: number) =>
    client.get<Market>(`/api/markets/${id}`),
}

// ─── ORDERS (P2P) ───
export const orders = {
  list: (params?: { market_id?: number; outcome_id?: number; status?: string }) =>
    client.get<Order[]>('/api/orders', { params }),

  get: (id: number) =>
    client.get<Order>(`/api/orders/${id}`),

  create: (data: { market_id: number; outcome_id: number; amount: string; odds: string }) =>
    client.post<Order>('/api/orders', data),

  cancel: (id: number) =>
    client.delete(`/api/orders/${id}`),

  match: (id: number, amount: string) =>
    client.post(`/api/orders/${id}/match`, { amount }),
}

// ─── CONTRACTS ───
export const contracts = {
  get: (id: number) =>
    client.get<Contract>(`/api/settlement/contracts/${id}`),

  claim: (id: number) =>
    client.post(`/api/settlement/contracts/${id}/claim`),

  dispute: (id: number) =>
    client.post(`/api/settlement/contracts/${id}/dispute`),
}

// ─── POOL MARKETS ───
export const poolMarkets = {
  state: (id: number) =>
    client.get<PoolState>(`/api/pool-markets/${id}/state`),

  bet: (id: number, outcome_id: number, amount: string) =>
    client.post(`/api/pool-markets/${id}/bet`, { outcome_id, amount }),

  myBets: (id: number, params?: { settled?: boolean; page?: number; page_size?: number }) =>
    client.get<PoolBet[]>(`/api/pool-markets/${id}/my-bets`, { params }),
}