'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Save } from 'lucide-react'

interface OptimizationRules {
  maxHistoryMessages: number
  includeSystemMessages: boolean
  maxTokensPerCall: number
  maxInputTokens: number | null
  aggressiveness: 'low' | 'medium' | 'high'
  preserveCodeBlocks: boolean
  preserveFormatting: boolean
  targetCostReduction: number
}

export default function SettingsPage() {
  const [rules, setRules] = useState<OptimizationRules>({
    maxHistoryMessages: 20,
    includeSystemMessages: true,
    maxTokensPerCall: 8000,
    maxInputTokens: null,
    aggressiveness: 'medium',
    preserveCodeBlocks: true,
    preserveFormatting: true,
    targetCostReduction: 0.3,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchRules()
  }, [])

  const fetchRules = async () => {
    try {
      const response = await fetch('/api/rules')
      if (response.ok) {
        const data = await response.json()
        setRules(data)
      }
    } catch (error) {
      toast.error('Failed to fetch optimization rules')
    } finally {
      setLoading(false)
    }
  }

  const saveRules = async () => {
    setSaving(true)
    try {
      const response = await fetch('/api/rules', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rules),
      })

      if (response.ok) {
        toast.success('Optimization rules saved')
      } else {
        toast.error('Failed to save optimization rules')
      }
    } catch (error) {
      toast.error('Failed to save optimization rules')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <p className="text-zinc-500">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-white">Optimization Settings</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Configure how the Token Optimizer processes your LLM requests
        </p>
      </div>

      <div className="max-w-2xl space-y-8">
        {/* History Settings */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">History Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-400">
                Max History Messages: {rules.maxHistoryMessages}
              </label>
              <input
                type="range"
                min="1"
                max="50"
                value={rules.maxHistoryMessages}
                onChange={(e) =>
                  setRules({ ...rules, maxHistoryMessages: parseInt(e.target.value) })
                }
                className="mt-2 w-full"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-zinc-400">Include System Messages</label>
              <input
                type="checkbox"
                checked={rules.includeSystemMessages}
                onChange={(e) =>
                  setRules({ ...rules, includeSystemMessages: e.target.checked })
                }
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>
        </div>

        {/* Token Limits */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Token Limits</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-400">Max Tokens Per Call</label>
              <input
                type="number"
                min="1"
                max="32000"
                value={rules.maxTokensPerCall}
                onChange={(e) =>
                  setRules({ ...rules, maxTokensPerCall: parseInt(e.target.value) })
                }
                className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-400">
                Max Input Tokens (optional)
              </label>
              <input
                type="number"
                min="1"
                value={rules.maxInputTokens || ''}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    maxInputTokens: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                placeholder="No limit"
                className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-white placeholder-zinc-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Optimization Preferences */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">
            Optimization Preferences
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-400 mb-3">Aggressiveness</label>
              <div className="flex gap-4">
                {['low', 'medium', 'high'].map((level) => (
                  <button
                    key={level}
                    onClick={() =>
                      setRules({
                        ...rules,
                        aggressiveness: level as 'low' | 'medium' | 'high',
                      })
                    }
                    className={`flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                      rules.aggressiveness === level
                        ? 'border-blue-500 bg-blue-600 text-white'
                        : 'border-zinc-700 bg-zinc-900 text-zinc-400 hover:bg-zinc-800'
                    }`}
                  >
                    {level.charAt(0).toUpperCase() + level.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-zinc-400">Preserve Code Blocks</label>
              <input
                type="checkbox"
                checked={rules.preserveCodeBlocks}
                onChange={(e) =>
                  setRules({ ...rules, preserveCodeBlocks: e.target.checked })
                }
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-zinc-400">Preserve Formatting</label>
              <input
                type="checkbox"
                checked={rules.preserveFormatting}
                onChange={(e) =>
                  setRules({ ...rules, preserveFormatting: e.target.checked })
                }
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>
        </div>

        {/* Cost Settings */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Cost Settings</h2>
          <div>
            <label className="block text-sm text-zinc-400">
              Target Cost Reduction: {(rules.targetCostReduction * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0"
              max="0.9"
              step="0.05"
              value={rules.targetCostReduction}
              onChange={(e) =>
                setRules({ ...rules, targetCostReduction: parseFloat(e.target.value) })
              }
              className="mt-2 w-full"
            />
          </div>
        </div>

        {/* Save Button */}
        <button
          onClick={saveRules}
          disabled={saving}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}
