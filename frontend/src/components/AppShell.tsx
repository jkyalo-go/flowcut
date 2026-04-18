import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import {
  Building2,
  CalendarRange,
  ChevronRight,
  FolderKanban,
  Inbox,
  LayoutDashboard,
  Menu,
  PlugZap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Toaster } from '@/components/ui/toaster'
import { useAuthStore } from '@/stores/authStore'
import { api, clearStoredToken } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Workspace } from '@/types'

const NAV = [
  {
    label: 'Overview',
    href: '/',
    icon: LayoutDashboard,
    match: (pathname: string) => pathname === '/',
  },
  {
    label: 'Projects',
    href: '/projects',
    icon: FolderKanban,
    match: (pathname: string) => pathname.startsWith('/projects') || pathname === '/editor',
  },
  {
    label: 'Queue',
    href: '/review-queue',
    icon: Inbox,
    match: (pathname: string) => pathname.startsWith('/review-queue'),
  },
  {
    label: 'Schedule',
    href: '/calendar',
    icon: CalendarRange,
    match: (pathname: string) => pathname.startsWith('/calendar'),
  },
  {
    label: 'Integrations',
    href: '/integrations',
    icon: PlugZap,
    match: (pathname: string) => pathname.startsWith('/integrations') || pathname.startsWith('/platforms') || pathname.startsWith('/ai-settings'),
  },
  {
    label: 'Workspace',
    href: '/workspace',
    icon: Building2,
    match: (pathname: string) => pathname.startsWith('/workspace') || pathname.startsWith('/billing') || pathname.startsWith('/admin') || pathname.startsWith('/style-profiles'),
  },
]

interface RailContentProps {
  activePath: string
  handleSignOut: () => Promise<void>
  handleSwitchWorkspace: (workspaceId: string) => Promise<void>
  initials: string
  isAdmin: boolean
  setMobileOpen: (open: boolean) => void
  userEmail?: string
  userName?: string
  workspace: Workspace | null
  workspaces: Workspace[]
}

function RailContent({
  activePath,
  handleSignOut,
  handleSwitchWorkspace,
  initials,
  isAdmin,
  setMobileOpen,
  userEmail,
  userName,
  workspace,
  workspaces,
}: RailContentProps) {
  return (
    <div className="flex h-full flex-col justify-between">
      <div className="space-y-8">
        <div className="rounded-[28px] border border-border/70 bg-card/95 p-5 shadow-[0_24px_80px_rgba(37,33,23,0.08)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-display text-lg tracking-tight text-foreground">FlowCut</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Editorial control for teams shipping on schedule.
              </p>
            </div>
            <div className="rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.16em] text-primary">
              {workspace?.plan_tier ?? 'starter'}
            </div>
          </div>

          <div className="mt-5">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" className="flex w-full items-center justify-between rounded-2xl border border-border/70 bg-background/70 px-4 py-3 text-left transition hover:border-primary/40 hover:bg-background">
                  <div>
                    <p className="text-sm font-medium text-foreground">{workspace?.name ?? 'Workspace'}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">Switch workspace</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-64">
                {workspaces.map((ws) => (
                  <DropdownMenuItem
                    key={ws.id}
                    onClick={() => handleSwitchWorkspace(ws.id)}
                    className={ws.id === workspace?.id ? 'font-medium' : ''}
                  >
                    {ws.name}
                    {ws.id === workspace?.id && (
                      <span className="ml-auto text-xs text-primary">Current</span>
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="space-y-2">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Workspace
          </p>
          <nav className="space-y-1">
            {NAV.map(({ label, href, icon: Icon, match }) => {
              const active = match(activePath)
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    'group flex items-center gap-3 rounded-2xl px-3 py-3 text-sm transition',
                    active
                      ? 'bg-foreground text-background shadow-[0_16px_40px_rgba(27,24,18,0.14)]'
                      : 'text-muted-foreground hover:bg-card hover:text-foreground',
                  )}
                >
                  <span className={cn(
                    'flex h-9 w-9 items-center justify-center rounded-xl border transition',
                    active
                      ? 'border-background/20 bg-background/10 text-background'
                      : 'border-border/60 bg-background/70 text-muted-foreground group-hover:border-primary/30 group-hover:text-primary',
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="font-medium">{label}</span>
                </Link>
              )
            })}
          </nav>
        </div>
      </div>

      <div className="rounded-[24px] border border-border/70 bg-card/90 p-4">
        <div className="flex items-center gap-3">
          <Avatar className="h-11 w-11 text-sm">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{userName ?? 'FlowCut user'}</p>
            <p className="truncate text-xs text-muted-foreground">{userEmail}</p>
          </div>
        </div>

        <div className="mt-4 flex gap-2">
          <Button variant="outline" size="sm" asChild className="flex-1 rounded-xl">
            <Link href={`/workspace${isAdmin ? '?tab=admin' : ''}`}>{isAdmin ? 'Admin' : 'Settings'}</Link>
          </Button>
          <Button variant="ghost" size="sm" onClick={() => void handleSignOut()} className="flex-1 rounded-xl">
            Sign out
          </Button>
        </div>
      </div>
    </div>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, workspace, clear, setWorkspace, setToken } = useAuthStore()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    api.get<Workspace[]>('/api/workspaces')
      .then((data) => setWorkspaces(Array.isArray(data) ? data : []))
      .catch(() => {
        void 0
      })
  }, [])

  async function handleSignOut() {
    try {
      await api.post('/api/auth/logout', {})
    } catch {
      void 0
    } finally {
      clearStoredToken()
      clear()
    }
    await router.replace('/login')
  }

  async function handleSwitchWorkspace(wsId: string) {
    if (wsId === workspace?.id) return
    try {
      const data = await api.post<{ token: string; user: { id: string; email: string; name: string }; workspace: Workspace }>(
        '/api/auth/switch-workspace',
        { workspace_id: wsId }
      )
      setToken(data.token)
      setWorkspace(data.workspace)
      router.replace('/')
    } catch {
      void 0
    }
  }

  const initials = user?.name
    ? user.name.split(' ').filter(w => w.length > 0).map(w => w[0].toUpperCase()).slice(0, 2).join('') || 'FC'
    : 'FC'

  const activeItem = useMemo(
    () => NAV.find((item) => item.match(router.pathname)) ?? NAV[0],
    [router.pathname],
  )

  const isAdmin = user?.user_type === 'admin'

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-[18rem] border-r border-border/70 bg-sidebar/80 px-5 py-6 backdrop-blur xl:flex">
        <RailContent
          activePath={router.pathname}
          handleSignOut={handleSignOut}
          handleSwitchWorkspace={handleSwitchWorkspace}
          initials={initials}
          isAdmin={isAdmin}
          setMobileOpen={setMobileOpen}
          userEmail={user?.email}
          userName={user?.name}
          workspace={workspace}
          workspaces={workspaces}
        />
      </aside>

      <div className="xl:pl-[18rem]">
        <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur">
          <div className="flex items-center justify-between px-4 py-4 md:px-6 xl:px-8">
            <div className="flex items-center gap-3">
              <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="icon" className="rounded-xl xl:hidden">
                    <Menu className="h-4 w-4" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-[18rem] border-r border-border/70 bg-sidebar p-0">
                  <SheetHeader className="sr-only">
                    <SheetTitle>Navigation</SheetTitle>
                    <SheetDescription>Open app navigation</SheetDescription>
                  </SheetHeader>
                  <div className="h-full px-5 py-6">
                    <RailContent
                      activePath={router.pathname}
                      handleSignOut={handleSignOut}
                      handleSwitchWorkspace={handleSwitchWorkspace}
                      initials={initials}
                      isAdmin={isAdmin}
                      setMobileOpen={setMobileOpen}
                      userEmail={user?.email}
                      userName={user?.name}
                      workspace={workspace}
                      workspaces={workspaces}
                    />
                  </div>
                </SheetContent>
              </Sheet>

              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                  {workspace?.name ?? 'Workspace'}
                </p>
                <h1 className="font-display text-2xl tracking-tight text-foreground">
                  {activeItem.label}
                </h1>
              </div>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" className="flex items-center gap-3 rounded-2xl border border-border/70 bg-card/80 px-3 py-2 transition hover:border-primary/30 hover:bg-card">
                  <Avatar className="h-9 w-9 text-xs">
                    <AvatarFallback>{initials}</AvatarFallback>
                  </Avatar>
                  <div className="hidden text-left sm:block">
                    <p className="max-w-[180px] truncate text-sm font-medium text-foreground">{user?.name ?? 'FlowCut user'}</p>
                    <p className="max-w-[180px] truncate text-xs text-muted-foreground">{user?.email}</p>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="bottom" align="end" className="w-56">
                <DropdownMenuItem asChild>
                  <Link href="/workspace">Workspace</Link>
                </DropdownMenuItem>
                {isAdmin && (
                  <DropdownMenuItem asChild>
                    <Link href="/workspace?tab=admin">Admin</Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleSignOut}>Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="px-4 py-5 md:px-6 md:py-6 xl:px-8">
          {children}
        </main>
      </div>

      <Toaster />
    </div>
  )
}
