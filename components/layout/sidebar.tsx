'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { signOut, useSession } from 'next-auth/react'
import {
  LayoutDashboard,
  BarChart3,
  DollarSign,
  ScrollText,
  Key,
  Settings,
  LogOut,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
  {
    section: 'BUILD',
    items: [
      { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    section: 'ANALYTICS',
    items: [
      { name: 'Usage', href: '/dashboard/analytics/usage', icon: BarChart3 },
      { name: 'Cost', href: '/dashboard/analytics/cost', icon: DollarSign },
      { name: 'Logs', href: '/dashboard/analytics/logs', icon: ScrollText },
    ],
  },
  {
    section: 'MANAGE',
    items: [
      { name: 'API keys', href: '/dashboard/keys', icon: Key },
      { name: 'Settings', href: '/dashboard/settings', icon: Settings },
    ],
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const { data: session } = useSession()

  return (
    <div className="flex h-screen w-60 flex-col bg-zinc-950 border-r border-zinc-800">
      {/* Logo */}
      <div className="flex h-16 items-center border-b border-zinc-800 px-6">
        <h1 className="text-lg font-semibold">Token Optimizer</h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-4">
        {navigation.map((group) => (
          <div key={group.section} className="mb-6">
            <h2 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              {group.section}
            </h2>
            <ul className="space-y-1">
              {group.items.map((item) => {
                const isActive = pathname === item.href
                return (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                        isActive
                          ? 'bg-zinc-800 text-white'
                          : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.name}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Documentation & User */}
      <div className="border-t border-zinc-800 p-4">
        <Link
          href="#"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-100"
        >
          <FileText className="h-4 w-4" />
          Documentation
        </Link>

        {session?.user && (
          <div className="mt-4 border-t border-zinc-800 pt-4">
            <div className="flex items-center justify-between gap-3 px-3 py-2">
              <div className="flex items-center gap-3 min-w-0">
                {session.user.image && (
                  <img
                    src={session.user.image}
                    alt={session.user.name || ''}
                    className="h-8 w-8 rounded-full"
                  />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-white truncate">
                    {session.user.name}
                  </p>
                  <p className="text-xs text-zinc-500 truncate">
                    {session.user.email}
                  </p>
                </div>
              </div>
              <button
                onClick={() => signOut({ callbackUrl: '/' })}
                className="shrink-0 rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-100"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
