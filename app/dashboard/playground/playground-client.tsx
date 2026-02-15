'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'

interface PlaygroundClientProps {
  userId: string
  userEmail: string
  apiKeys: Array<{
    id: string
    name: string
    keyPrefix: string
  }>
}

export default function PlaygroundClient({ userId, userEmail, apiKeys }: PlaygroundClientProps) {
  const [selectedKeyId, setSelectedKeyId] = useState(apiKeys[0]?.id || '')
  const [apiKey, setApiKey] = useState('')
  const [message, setMessage] = useState('')
  const [model, setModel] = useState('gpt-4o-mini')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const handleTest = async () => {
    if (!selectedKeyId) {
      setError('Please select an API key')
      return
    }

    if (!apiKey.trim()) {
      setError('Please paste your API key')
      return
    }

    if (!message.trim()) {
      setError('Please enter a message')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch('/api/playground/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyId: selectedKeyId,
          apiKey: apiKey.trim(),
          message: message.trim(),
          model,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Test failed')
      }

      setResult(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (apiKeys.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
        <p className="text-sm text-zinc-400">
          No API keys found. Please create one first in the{' '}
          <a href="/dashboard/keys" className="text-blue-400 hover:underline">
            API Keys
          </a>{' '}
          page.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* User Info */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3.5">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-zinc-500 text-xs">User ID:</span>
            <p className="mt-0.5 font-mono text-xs text-white">{userId}</p>
          </div>
          <div>
            <span className="text-zinc-500 text-xs">Email:</span>
            <p className="mt-0.5 text-xs text-white">{userEmail}</p>
          </div>
        </div>
      </div>

      {/* Test Form */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5 space-y-3.5">
        {/* API Key Selection */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            API Key
          </label>
          <select
            value={selectedKeyId}
            onChange={(e) => setSelectedKeyId(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          >
            {apiKeys.map((key) => (
              <option key={key.id} value={key.id}>
                {key.name} ({key.keyPrefix})
              </option>
            ))}
          </select>
        </div>

        {/* API Key Input */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            Paste Your API Key
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="tok_..."
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-blue-500 focus:outline-none font-mono"
          />
          <p className="mt-1.5 text-xs text-zinc-500">
            Your API key is used only for this test and is not stored
          </p>
        </div>

        {/* Model Selection */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            Model
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          >
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
          </select>
        </div>

        {/* Message Input */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            Message
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your message here..."
            rows={4}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Error Display */}
        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Test Button */}
        <button
          onClick={handleTest}
          disabled={loading}
          className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors mt-1"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Testing...
            </>
          ) : (
            '🚀 Test Optimization'
          )}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-5 space-y-3.5">
          <h2 className="text-base font-semibold text-white">Results</h2>

          {/* Stats Comparison */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <p className="text-xs text-zinc-500 mb-1">Original</p>
              <p className="text-2xl font-bold text-white">{result.stats.original_tokens}</p>
              <p className="text-xs text-zinc-400 mt-1">${result.stats.original_cost.toFixed(6)}</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <p className="text-xs text-zinc-500 mb-1">Optimized</p>
              <p className="text-2xl font-bold text-green-400">{result.stats.optimized_tokens}</p>
              <p className="text-xs text-zinc-400 mt-1">${result.stats.optimized_cost.toFixed(6)}</p>
            </div>
          </div>

          {/* Savings */}
          <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-4">
            <p className="text-sm font-medium text-green-400">
              💰 Saved {result.stats.tokens_saved} tokens ({result.stats.savings_percent}%) • ${result.stats.cost_saved.toFixed(6)}
            </p>
            <div className="mt-2 h-2 rounded-full bg-zinc-800 overflow-hidden">
              <div
                className="h-full bg-green-500 transition-all"
                style={{ width: `${result.stats.savings_percent}%` }}
              />
            </div>
          </div>

          {/* Response */}
          <div>
            <p className="text-sm font-medium text-zinc-300 mb-2">AI Response:</p>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <p className="text-sm text-white whitespace-pre-wrap">{result.response}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
