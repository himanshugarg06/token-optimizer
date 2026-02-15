import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { prisma } from '@/lib/prisma'
import bcrypt from 'bcryptjs'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://token-optimizer-backend-production.up.railway.app'

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions)

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const { keyId, apiKey, message, model } = body

    if (!keyId || !apiKey || !message || !model) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    // Get the API key from database
    const apiKeyRecord = await prisma.apiKey.findUnique({
      where: { id: keyId },
      select: {
        userId: true,
        keyHash: true,
        isActive: true,
      },
    })

    if (!apiKeyRecord || !apiKeyRecord.isActive) {
      return NextResponse.json({ error: 'Invalid API key' }, { status: 400 })
    }

    if (apiKeyRecord.userId !== session.user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }

    // Verify the provided API key matches the hash
    const isValidKey = await bcrypt.compare(apiKey, apiKeyRecord.keyHash)
    if (!isValidKey) {
      return NextResponse.json({ error: 'Invalid API key' }, { status: 401 })
    }

    // Use optimizer stats if available; fallback to rough estimate
    const backendData = await backendResponse.json()
    const optimizerStats = backendData.optimizer?.stats || {}
    const originalTokens = optimizerStats.tokens_before ?? Math.ceil(message.length / 4)

    // Extract the response and stats
    const response = backendData.choices?.[0]?.message?.content || 'No response'

    // Calculate costs (approximate) using backend token counts
    const costPerTokenInput = 0.00000015 // $0.15 per 1M tokens for gpt-4o-mini
    const optimizedTokens = optimizerStats.tokens_after ?? originalTokens
    const optimizedCost = optimizedTokens * costPerTokenInput
    const originalCost = originalTokens * costPerTokenInput
    const tokensSaved = Math.max(0, originalTokens - optimizedTokens)
    const costSaved = Math.max(0, originalCost - optimizedCost)
    const savingsPercent = originalTokens > 0 ? Math.max(0, Math.round((tokensSaved / originalTokens) * 100)) : 0

    return NextResponse.json({
      response,
      stats: {
        original_tokens: originalTokens,
        optimized_tokens: optimizedTokens,
        tokens_saved: tokensSaved,
        savings_percent: savingsPercent,
        original_cost: originalCost,
        optimized_cost: optimizedCost,
        cost_saved: costSaved,
      },
      optimizer: optimizerStats,
    })
  } catch (error: any) {
    console.error('Playground test error:', error)
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    )
  }
}
