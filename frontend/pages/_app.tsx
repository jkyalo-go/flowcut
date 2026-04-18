// frontend/pages/_app.tsx
import type { AppProps } from 'next/app'
import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { IBM_Plex_Mono, IBM_Plex_Sans, Space_Grotesk } from 'next/font/google'
import '@/styles/globals.css'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { AppShell } from '@/components/AppShell'
import { useAuthStore } from '@/stores/authStore'
import { api, ApiError, setUnauthorizedHandler } from '@/lib/api'
import type { User, Workspace } from '@/types'

const PUBLIC_PATHS = ['/login', '/register', '/invitations', '/auth']

const displayFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
})

const bodyFont = IBM_Plex_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
})

const monoFont = IBM_Plex_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
  weight: ['400', '500'],
})

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()
  const { user, isLoading, setUser, setWorkspace, setToken, setLoading } = useAuthStore()

  useEffect(() => {
    // Install global 401 handler: any unauthorized response from the API
    // clears local state and redirects to /login. Without this, the user
    // sees a "logged in" UI while every fetch fails.
    setUnauthorizedHandler(() => {
      const { clear } = useAuthStore.getState()
      clear()
      if (!PUBLIC_PATHS.some(p => router.pathname.startsWith(p))) {
        const redirect = encodeURIComponent(router.asPath)
        void router.replace(`/login?redirect=${redirect}`)
      }
    })
    return () => setUnauthorizedHandler(null)
  }, [router])

  useEffect(() => {
    async function bootstrap() {
      try {
        const data = await api.get<{ token: string; user: User; workspace: Workspace }>('/api/auth/me')
        setUser(data.user)
        setWorkspace(data.workspace)
        setToken(data.token)
      } catch (e) {
        // Bootstrap is best-effort: any non-success means "treat as signed-out".
        // This covers 401 (no session), 5xx (backend cold/down in dev), and
        // network errors. We log at info-level for diagnostics but do not
        // surface to the dev error overlay — an unauthenticated user with a
        // dead backend is not a React/runtime error.
        if (e instanceof ApiError) {
          if (e.status !== 401) {
            console.info('[bootstrap] backend returned', e.status, '— treating as unauthenticated')
          }
        } else {
          console.info('[bootstrap] network error, continuing as unauthenticated:', e)
        }
      } finally {
        setLoading(false)
      }
    }
    bootstrap()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const isPublicPath = PUBLIC_PATHS.some(p => router.pathname.startsWith(p))

  useEffect(() => {
    if (isLoading || isPublicPath || user) return
    void router.replace('/login')
  }, [isLoading, isPublicPath, router, user])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background px-6">
        <div className="app-panel w-full max-w-md p-6 text-center">
          <p className="eyebrow">FlowCut</p>
          <p className="mt-3 text-sm text-muted-foreground">Restoring your workspace session…</p>
        </div>
      </div>
    )
  }

  if (!user && !isPublicPath) {
    return (
      <div className="flex h-screen items-center justify-center bg-background px-6">
        <div className="app-panel w-full max-w-md p-6 text-center">
          <p className="eyebrow">Authentication</p>
          <p className="mt-3 text-sm text-muted-foreground">Redirecting to sign in…</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${displayFont.variable} ${bodyFont.variable} ${monoFont.variable}`}>
      <ErrorBoundary>
        {isPublicPath ? (
          <Component {...pageProps} />
        ) : (
          <AppShell>
            <Component {...pageProps} />
          </AppShell>
        )}
      </ErrorBoundary>
    </div>
  )
}
