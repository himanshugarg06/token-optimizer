'use client'

import { useEffect, useState } from 'react'
import { BarChart3 } from 'lucide-react'

interface UsageData {
  date: string
  originalTokens: number
  optimizedTokens: number
  tokensSaved: number
}

export default function UsagePage() {
  const [data, setData] = useState<UsageData[]>([])
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('30d')

  useEffect(() => {
    fetchData()
  }, [period])

  const fetchData = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/analytics/usage?period=${period}`)
      if (response.ok) {
        const result = await response.json()
        setData(result)
      }
    } catch (error) {
      console.error('Failed to fetch usage data:', error)
    } finally {
      setLoading(false)
    }
  }

  const maxTokens = Math.max(...data.map(d => d.originalTokens), 1)

  return (
    <div className="min-h-screen bg-black p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-white">Token Usage</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Track your token usage and optimization over time
          </p>
        </div>
        <div className="flex gap-2">
          {['7d', '30d', '90d'].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'border border-zinc-700 bg-zinc-900 text-zinc-400 hover:bg-zinc-800'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-96 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950">
          <p className="text-zinc-500">Loading...</p>
        </div>
      ) : data.length === 0 ? (
        <div className="flex h-96 flex-col items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950">
          <BarChart3 className="mb-4 h-12 w-12 text-zinc-700" />
          <p className="text-zinc-500">No usage data yet</p>
          <p className="mt-2 text-sm text-zinc-600">
            Start making API calls to see your usage analytics
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Summary Stats */}
          <div className="grid gap-6 sm:grid-cols-3">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
              <p className="text-sm text-zinc-500">Total Original Tokens</p>
              <p className="mt-2 text-3xl font-semibold text-white">
                {data.reduce((sum, d) => sum + d.originalTokens, 0).toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
              <p className="text-sm text-zinc-500">Total Optimized Tokens</p>
              <p className="mt-2 text-3xl font-semibold text-white">
                {data.reduce((sum, d) => sum + d.optimizedTokens, 0).toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
              <p className="text-sm text-zinc-500">Total Tokens Saved</p>
              <p className="mt-2 text-3xl font-semibold text-green-500">
                {data.reduce((sum, d) => sum + d.tokensSaved, 0).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Chart */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <h2 className="mb-6 text-lg font-semibold text-white">Daily Usage</h2>
            <div className="space-y-4">
              {data.map((item) => (
                <div key={item.date} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-zinc-400">
                      {new Date(item.date).toLocaleDateString()}
                    </span>
                    <span className="text-white">
                      {item.tokensSaved.toLocaleString()} saved
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <div className="h-8 overflow-hidden rounded bg-zinc-900">
                        <div
                          className="h-full bg-blue-500"
                          style={{
                            width: `${(item.originalTokens / maxTokens) * 100}%`,
                          }}
                        />
                      </div>
                      <p className="mt-1 text-xs text-zinc-600">
                        Original: {item.originalTokens.toLocaleString()}
                      </p>
                    </div>
                    <div className="flex-1">
                      <div className="h-8 overflow-hidden rounded bg-zinc-900">
                        <div
                          className="h-full bg-green-500"
                          style={{
                            width: `${(item.optimizedTokens / maxTokens) * 100}%`,
                          }}
                        />
                      </div>
                      <p className="mt-1 text-xs text-zinc-600">
                        Optimized: {item.optimizedTokens.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
