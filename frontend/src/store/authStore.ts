import { create } from 'zustand'
import type { User } from '@/types/api'
import { auth } from '@/api/endpoints'

interface AuthState {
  user: User | null
  isLoading: boolean
  error: string | null

  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await auth.login(email, password)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      set({ user: data.user, isLoading: false })
    } catch (e: any) {
      const msg = e.response?.data?.detail || 'Login failed'
      set({ error: msg, isLoading: false })
    }
  },

  register: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await auth.register(email, password)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      set({ user: data.user, isLoading: false })
    } catch (e: any) {
      const msg = e.response?.data?.detail || 'Registration failed'
      set({ error: msg, isLoading: false })
    }
  },

  logout: () => {
    localStorage.clear()
    set({ user: null, error: null })
  },

  fetchMe: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    set({ isLoading: true })
    try {
      const { data } = await auth.me()
      set({ user: data, isLoading: false })
    } catch {
      localStorage.clear()
      set({ user: null, isLoading: false })
    }
  },

  clearError: () => set({ error: null }),
}))