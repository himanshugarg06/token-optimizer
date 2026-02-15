'use client'

import { useEffect, useState } from 'react'
import { Plus, Copy, Trash2, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'

interface ApiKey {
  id: string
  name: string
  keyPrefix: string
  lastUsedAt: string | null
  createdAt: string
  expiresAt: string | null
  isActive: boolean
  key?: string // Only present on creation
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<ApiKey | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    fetchKeys()
  }, [])

  const fetchKeys = async () => {
    try {
      const response = await fetch('/api/keys')
      if (response.ok) {
        const data = await response.json()
        setKeys(data)
      }
    } catch (error) {
      toast.error('Failed to fetch API keys')
    } finally {
      setLoading(false)
    }
  }

  const createKey = async () => {
    if (!newKeyName.trim()) {
      toast.error('Please enter a key name')
      return
    }

    setCreating(true)
    try {
      const response = await fetch('/api/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName }),
      })

      if (response.ok) {
        const data = await response.json()
        setCreatedKey(data)
        setNewKeyName('')
        setShowCreateModal(false)
        fetchKeys()
      } else {
        toast.error('Failed to create API key')
      }
    } catch (error) {
      toast.error('Failed to create API key')
    } finally {
      setCreating(false)
    }
  }

  const deleteKey = async (id: string) => {
    if (!confirm('Are you sure you want to delete this API key?')) return

    try {
      const response = await fetch(`/api/keys/${id}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        toast.success('API key deleted')
        fetchKeys()
      } else {
        toast.error('Failed to delete API key')
      }
    } catch (error) {
      toast.error('Failed to delete API key')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
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
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-white">API Keys</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Manage your API keys for accessing the Token Optimizer API
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Create New Key
        </button>
      </div>

      {/* Keys List */}
      {keys.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-12 text-center">
          <p className="text-zinc-500">No API keys yet</p>
          <p className="mt-2 text-sm text-zinc-600">
            Create your first API key to start using the Token Optimizer
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {keys.map((key) => (
            <div
              key={key.id}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950 p-6"
            >
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-medium text-white">{key.name}</h3>
                  {!key.isActive && (
                    <span className="rounded-full bg-red-500/10 px-2 py-1 text-xs text-red-500">
                      Inactive
                    </span>
                  )}
                </div>
                <div className="mt-2 flex items-center gap-4 text-sm text-zinc-500">
                  <span className="font-mono">{key.keyPrefix}...</span>
                  <span>
                    Created {new Date(key.createdAt).toLocaleDateString()}
                  </span>
                  {key.lastUsedAt && (
                    <span>
                      Last used {new Date(key.lastUsedAt).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => copyToClipboard(key.keyPrefix)}
                  className="rounded-lg border border-zinc-700 bg-zinc-900 p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                  title="Copy prefix"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={() => deleteKey(key.id)}
                  className="rounded-lg border border-zinc-700 bg-zinc-900 p-2 text-zinc-400 transition-colors hover:bg-red-900 hover:text-red-400"
                  title="Delete key"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Key Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
          <div className="w-full max-w-md rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <h2 className="text-xl font-semibold text-white">Create API Key</h2>
            <p className="mt-2 text-sm text-zinc-500">
              Give your API key a descriptive name
            </p>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g., Production API Key"
              className="mt-4 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-white placeholder-zinc-600 focus:border-blue-500 focus:outline-none"
              onKeyPress={(e) => e.key === 'Enter' && createKey()}
            />
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setNewKeyName('')
                }}
                className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
                disabled={creating}
              >
                Cancel
              </button>
              <button
                onClick={createKey}
                className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                disabled={creating}
              >
                {creating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Show Created Key Modal */}
      {createdKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
          <div className="w-full max-w-md rounded-lg border border-zinc-800 bg-zinc-950 p-6">
            <div className="mb-4 flex items-center gap-3">
              <CheckCircle2 className="h-6 w-6 text-green-500" />
              <h2 className="text-xl font-semibold text-white">API Key Created</h2>
            </div>
            <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4">
              <p className="text-sm text-yellow-500">
                Make sure to copy your API key now. You won't be able to see it again!
              </p>
            </div>
            <div className="mt-4">
              <label className="text-sm text-zinc-500">Your API Key</label>
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={createdKey.key}
                  readOnly
                  className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 font-mono text-sm text-white"
                />
                <button
                  onClick={() => copyToClipboard(createdKey.key!)}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Copy className="h-4 w-4" />
                </button>
              </div>
            </div>
            <button
              onClick={() => setCreatedKey(null)}
              className="mt-6 w-full rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
