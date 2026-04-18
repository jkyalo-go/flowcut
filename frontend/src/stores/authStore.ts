// frontend/src/stores/authStore.ts
import { create } from 'zustand'
import type { User, Workspace } from '@/types'

interface AuthState {
  user: User | null
  workspace: Workspace | null
  token: string | null
  isLoading: boolean
  setUser: (user: User | null) => void
  setWorkspace: (workspace: Workspace | null) => void
  setToken: (token: string | null) => void
  setLoading: (v: boolean) => void
  clear: () => void
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  workspace: null,
  token: null,
  isLoading: true,
  setUser: (user) => set({ user }),
  setWorkspace: (workspace) => set({ workspace }),
  setToken: (token) => set({ token }),
  setLoading: (isLoading) => set({ isLoading }),
  clear: () => set({ user: null, workspace: null, token: null }),
}))
