// frontend/src/components/AppShell.tsx
import Link from 'next/link'
import { useRouter } from 'next/router'
import {
  Sidebar, SidebarContent, SidebarHeader, SidebarMenu, SidebarMenuItem,
  SidebarMenuButton, SidebarProvider, SidebarTrigger,
} from '@/components/ui/sidebar'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Toaster } from '@/components/ui/toaster'
import { useAuthStore } from '@/stores/authStore'
import { clearStoredToken } from '@/lib/api'

const NAV = [
  { label: 'Editor', href: '/' },
  { label: 'Review Queue', href: '/review-queue' },
  { label: 'Calendar', href: '/calendar' },
  { label: 'Platforms', href: '/platforms' },
  { label: 'Style Profiles', href: '/style-profiles' },
  { label: 'AI Settings', href: '/ai-settings' },
  { label: 'Billing', href: '/billing' },
  { label: 'Workspace', href: '/workspace' },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, clear } = useAuthStore()

  function handleSignOut() {
    clearStoredToken()
    clear()
    router.replace('/login')
  }

  const initials = user?.name?.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2) ?? 'FC'

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden">
        <Sidebar>
          <SidebarHeader className="px-4 py-3 text-sm font-semibold tracking-tight">
            FlowCut
          </SidebarHeader>
          <SidebarContent>
            <SidebarMenu>
              {NAV.map(({ label, href }) => (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton asChild isActive={router.pathname === href}>
                    <Link href={href}>
                      <span>{label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarContent>
          <div className="mt-auto p-3 border-t">
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-2 w-full rounded-md p-2 hover:bg-accent">
                <Avatar className="h-6 w-6 text-xs">
                  <AvatarFallback>{initials}</AvatarFallback>
                </Avatar>
                <span className="text-sm truncate">{user?.email}</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-48">
                <DropdownMenuItem onClick={handleSignOut}>Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </Sidebar>
        <main className="flex-1 overflow-auto">
          <div className="flex items-center gap-2 p-2 border-b md:hidden">
            <SidebarTrigger />
          </div>
          {children}
        </main>
      </div>
      <Toaster />
    </SidebarProvider>
  )
}
