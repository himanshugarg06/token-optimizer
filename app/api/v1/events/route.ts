import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

const SHARED_SECRET = process.env.DASHBOARD_API_KEY || process.env.MIDDLEWARE_API_KEY || ''
const COST_PER_TOKEN = 0.00000015 // rough default; keep small to avoid over-reporting

export async function POST(request: NextRequest) {
  try {
    const secret = request.headers.get('x-api-key')
    if (!SHARED_SECRET || secret !== SHARED_SECRET) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const {
      tenant_id,
      project_id,
      api_key_prefix,
      model = 'unknown',
      endpoint = '/v1/chat',
      stats = {},
    } = body

    if (!api_key_prefix) {
      return NextResponse.json({ error: 'api_key_prefix required' }, { status: 400 })
    }

    // Find matching API key by prefix (best-effort)
    const apiKeyRecord = await prisma.apiKey.findFirst({
      where: { keyPrefix: api_key_prefix, isActive: true },
      select: { id: true, userId: true },
    })

    if (!apiKeyRecord) {
      return NextResponse.json({ error: 'API key not found' }, { status: 404 })
    }

    const tokensBefore = stats.tokens_before ?? 0
    const tokensAfter = stats.tokens_after ?? 0
    const tokensSaved = stats.tokens_saved ?? (tokensBefore - tokensAfter)

    const originalCost = tokensBefore * COST_PER_TOKEN
    const optimizedCost = tokensAfter * COST_PER_TOKEN
    const costSaved = originalCost - optimizedCost

    await prisma.usageRecord.create({
      data: {
        userId: apiKeyRecord.userId,
        apiKeyId: apiKeyRecord.id,
        model,
        endpoint,
        originalInputTokens: tokensBefore,
        originalOutputTokens: 0,
        optimizedInputTokens: tokensAfter,
        optimizedOutputTokens: 0,
        tokensSaved: tokensSaved,
        originalCost,
        optimizedCost,
        costSaved,
        latencyMs: stats.latency_ms ?? null,
        success: true,
        errorMessage: null,
      },
    })

    return NextResponse.json({ status: 'ok' })
  } catch (error) {
    console.error('Event ingest error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
