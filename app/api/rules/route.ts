import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { prisma } from '@/lib/prisma'
import { z } from 'zod'

const updateRulesSchema = z.object({
  maxHistoryMessages: z.number().int().min(1).max(50),
  includeSystemMessages: z.boolean(),
  maxTokensPerCall: z.number().int().min(1).max(32000),
  maxInputTokens: z.number().int().min(1).optional().nullable(),
  aggressiveness: z.enum(['low', 'medium', 'high']),
  preserveCodeBlocks: z.boolean(),
  preserveFormatting: z.boolean(),
  targetCostReduction: z.number().min(0).max(0.9),
})

// Default optimization rules
const defaultRules = {
  maxHistoryMessages: 20,
  includeSystemMessages: true,
  maxTokensPerCall: 8000,
  maxInputTokens: null,
  aggressiveness: 'medium' as const,
  preserveCodeBlocks: true,
  preserveFormatting: true,
  targetCostReduction: 0.3,
}

// GET /api/rules - Get optimization rules for authenticated user
export async function GET() {
  try {
    const session = await getServerSession(authOptions)

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const rules = await prisma.optimizationRule.findFirst({
      where: {
        userId: session.user.id,
      },
    })

    // Return user's rules or default rules if none exist
    return NextResponse.json(rules || defaultRules)
  } catch (error) {
    console.error('Error fetching optimization rules:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

// PUT /api/rules - Update optimization rules
export async function PUT(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions)

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const validatedData = updateRulesSchema.parse(body)

    // Upsert: create if doesn't exist, update if exists
    const rules = await prisma.optimizationRule.upsert({
      where: {
        userId: session.user.id,
      },
      update: validatedData,
      create: {
        userId: session.user.id,
        ...validatedData,
      },
    })

    return NextResponse.json(rules)
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Validation error', details: error.issues },
        { status: 400 }
      )
    }
    console.error('Error updating optimization rules:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
