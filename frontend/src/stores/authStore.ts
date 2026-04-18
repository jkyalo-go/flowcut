// frontend/src/stores/authStore.ts
//
// Token is NOT stored in memory. The session token lives in the httpOnly
// `flowcut_session` cookie (set by the backend) and is automatically attached
// to every API request via `credentials: "include"`. Keeping a second copy in
// JS-readable state would expose it to XSS.
//
// `setToken` is kept as a no-op for backward compatibility with existing call
// sites across the app — callers can still invoke it without breaking, and
// the authoritative token is always the cookie.
import { create } from 'zustand'
import type { User, Workspace } from '@/types'

interface AuthState {
  user: User | null
  workspace: Workspace | null
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
  isLoading: true,
  setUser: (user) => set({ user }),
  setWorkspace: (workspace) => set({ workspace }),
  setToken: (_token) => {
    // No-op by design: the token lives in an httpOnly cookie, never in JS memory.
    void _token
  },
  setLoading: (isLoading) => set({ isLoading }),
  clear: () => set({ user: null, workspace: null }),
}))
