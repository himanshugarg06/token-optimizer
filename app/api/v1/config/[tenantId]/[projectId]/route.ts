import { NextRequest, NextResponse } from 'next/server'

// Simple config endpoint to satisfy backend fetches.
// Protect with shared secret header.

const SHARED_SECRET = process.env.DASHBOARD_API_KEY || process.env.MIDDLEWARE_API_KEY || ''

const defaultConfig = {
  maxHistoryMessages: 20,
  includeSystemMessages: true,
  maxTokensPerCall: 8000,
  maxInputTokens: null,
  aggressiveness: 'medium',
  preserveCodeBlocks: true,
  preserveFormatting: true,
  targetCostReduction: 0.3,
}

export async function GET(request: NextRequest) {
  const secret = request.headers.get('x-api-key')
  if (!SHARED_SECRET || secret !== SHARED_SECRET) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  return NextResponse.json({ config: defaultConfig })
}
