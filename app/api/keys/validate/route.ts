import { NextRequest, NextResponse } from 'next/server'
import bcrypt from 'bcryptjs'
import { prisma } from '@/lib/prisma'
import { getKeyPrefix } from '@/lib/auth/api-keys'

// POST /api/keys/validate
// Body: { apiKey: string }
// Public: used by backend for key validation; protect via key hash comparison
export async function POST(request: NextRequest) {
  try {
    const { apiKey } = await request.json()

    if (!apiKey || typeof apiKey !== 'string') {
      return NextResponse.json({ valid: false, error: 'apiKey is required' }, { status: 400 })
    }

    const keyPrefix = getKeyPrefix(apiKey)

    // Narrow search by prefix, then compare bcrypt hash
    const candidates = await prisma.apiKey.findMany({
      where: {
        keyPrefix,
        isActive: true,
      },
      select: {
        id: true,
        userId: true,
        keyHash: true,
      },
    })

    for (const candidate of candidates) {
      const isMatch = await bcrypt.compare(apiKey, candidate.keyHash)
      if (isMatch) {
        return NextResponse.json({
          valid: true,
          userId: candidate.userId,
          apiKeyId: candidate.id,
          keyPrefix,
        })
      }
    }

    return NextResponse.json({ valid: false, error: 'Invalid API key' }, { status: 401 })
  } catch (error) {
    console.error('Key validation error:', error)
    return NextResponse.json({ valid: false, error: 'Internal server error' }, { status: 500 })
  }
}
