import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'
import { Key, TrendingUp, DollarSign } from 'lucide-react'
import Link from 'next/link'

async function getDashboardData(userId: string) {
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  const [stats, recentActivity] = await Promise.all([
    prisma.usageRecord.aggregate({
      where: {
        userId,
        timestamp: { gte: thirtyDaysAgo },
        success: true,
      },
      _sum: {
        tokensSaved: true,
        costSaved: true,
      },
      _count: true,
    }),
    prisma.usageRecord.findMany({
      where: { userId },
      orderBy: { timestamp: 'desc' },
      take: 5,
      include: {
        apiKey: {
          select: {
            name: true,
            keyPrefix: true,
          },
        },
      },
    }),
  ])

  return {
    totalCalls: stats._count,
    tokensSaved: stats._sum.tokensSaved || 0,
    costSaved: stats._sum.costSaved || 0,
    recentActivity,
  }
}

function getGreeting(name: string) {
  const hour = new Date().getHours()
  if (hour < 12) return `Good morning, ${name}`
  if (hour < 18) return `Good afternoon, ${name}`
  return `Good evening, ${name}`
}

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)

  if (!session?.user) {
    redirect('/auth/signin')
  }

  const data = await getDashboardData(session.user.id)
  const firstName = session.user.name?.split(' ')[0] || 'there'

  return (
    <div className="min-h-screen bg-black p-8">
      {/* Greeting */}
      <div className="mb-12">
        <h1 className="text-4xl font-medium text-zinc-100 mb-8">
          {getGreeting(firstName)}
        </h1>

        {/* Quick Actions */}
        <div className="flex gap-4">
          <Link
            href="/dashboard/keys"
            className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
          >
            <Key className="h-4 w-4" />
            Get API Key
          </Link>
          <Link
            href="/dashboard/settings"
            className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
          >
            Configure Rules
          </Link>
          <Link
            href="/dashboard/analytics/usage"
            className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
          >
            View Analytics
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="mb-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-500">Total API Calls</p>
              <p className="mt-2 text-3xl font-semibold text-white">
                {data.totalCalls.toLocaleString()}
              </p>
              <p className="mt-1 text-xs text-zinc-600">Last 30 days</p>
            </div>
            <div className="rounded-full bg-zinc-900 p-3">
              <TrendingUp className="h-6 w-6 text-blue-500" />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-500">Tokens Saved</p>
              <p className="mt-2 text-3xl font-semibold text-white">
                {data.tokensSaved.toLocaleString()}
              </p>
              <p className="mt-1 text-xs text-zinc-600">Last 30 days</p>
            </div>
            <div className="rounded-full bg-zinc-900 p-3">
              <TrendingUp className="h-6 w-6 text-green-500" />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-500">Cost Savings</p>
              <p className="mt-2 text-3xl font-semibold text-white">
                ${data.costSaved.toFixed(2)}
              </p>
              <p className="mt-1 text-xs text-zinc-600">Last 30 days</p>
            </div>
            <div className="rounded-full bg-zinc-900 p-3">
              <DollarSign className="h-6 w-6 text-emerald-500" />
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Recent Activity</h2>
        {data.recentActivity.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-zinc-500">No API calls yet</p>
            <p className="mt-2 text-sm text-zinc-600">
              Create an API key and start optimizing your LLM requests
            </p>
            <Link
              href="/dashboard/keys"
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              <Key className="h-4 w-4" />
              Create API Key
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {data.recentActivity.map((record) => (
              <div
                key={record.id}
                className="flex items-center justify-between rounded-lg border border-zinc-800 bg-black p-4"
              >
                <div>
                  <p className="text-sm font-medium text-white">{record.model}</p>
                  <p className="text-xs text-zinc-500">
                    {record.apiKey?.name} ({record.apiKey?.keyPrefix})
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-white">
                    {record.tokensSaved.toLocaleString()} tokens saved
                  </p>
                  <p className="text-xs text-zinc-500">
                    {new Date(record.timestamp).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
