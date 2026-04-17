// frontend/src/stores/authStore.ts
import { create } from 'zustand'
import type { User, Workspace } from '@/types'

interface AuthState {
  user: User | null
  workspace: Workspace | null
  isLoading: boolean
  setUser: (user: User | null) => void
  setWorkspace: (workspace: Workspace | null) => void
  setLoading: (v: boolean) => void
  clear: () => void
}

// No persist middleware — auth re-hydrates from session cookie on every load.
// Persisting to localStorage would expose user_type/workspace_id to XSS.
export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  workspace: null,
  isLoading: true,
  setUser: (user) => set({ user }),
  setWorkspace: (workspace) => set({ workspace }),
  setLoading: (isLoading) => set({ isLoading }),
  clear: () => set({ user: null, workspace: null }),
}))
