// frontend/pages/_app.tsx
import type { AppProps } from 'next/app'
import { useEffect } from 'react'
import { useRouter } from 'next/router'
import '@/styles/globals.css'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useAuthStore } from '@/stores/authStore'
import { api, ApiError } from '@/lib/api'
import type { User, Workspace } from '@/types'

const PUBLIC_PATHS = ['/login', '/invitations']

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()
  const { user, isLoading, setUser, setWorkspace, setLoading } = useAuthStore()

  useEffect(() => {
    async function bootstrap() {
      try {
        const data = await api.get<{ user: User; workspace: Workspace }>('/api/auth/me')
        setUser(data.user)
        setWorkspace(data.workspace)
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 401)) {
          console.error('[bootstrap] auth check failed:', e)
        }
      } finally {
        setLoading(false)
      }
    }
    bootstrap()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const isPublicPath = PUBLIC_PATHS.some(p => router.pathname.startsWith(p))

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    )
  }

  if (!user && !isPublicPath) {
    if (typeof window !== 'undefined') {
      router.replace('/login')
    }
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Redirecting...
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <Component {...pageProps} />
    </ErrorBoundary>
  )
}
