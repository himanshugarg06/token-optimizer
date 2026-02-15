import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { prisma } from '@/lib/prisma'

// GET /api/analytics/usage - Token usage over time
export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions)

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { searchParams } = new URL(request.url)
    const period = searchParams.get('period') || '7d'

    // Calculate date range
    const daysMap: Record<string, number> = {
      '7d': 7,
      '30d': 30,
      '90d': 90,
    }
    const days = daysMap[period] || 7
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - days)

    // Fetch usage records
    const records = await prisma.usageRecord.findMany({
      where: {
        userId: session.user.id,
        timestamp: {
          gte: startDate,
        },
        success: true,
      },
      orderBy: {
        timestamp: 'asc',
      },
    })

    // Group by date
    const usageByDate = records.reduce((acc, record) => {
      const date = record.timestamp.toISOString().split('T')[0]
      if (!acc[date]) {
        acc[date] = {
          date,
          originalTokens: 0,
          optimizedTokens: 0,
          tokensSaved: 0,
        }
      }
      acc[date].originalTokens += record.originalInputTokens + record.originalOutputTokens
      acc[date].optimizedTokens += record.optimizedInputTokens + record.optimizedOutputTokens
      acc[date].tokensSaved += record.tokensSaved
      return acc
    }, {} as Record<string, any>)

    const result = Object.values(usageByDate)

    return NextResponse.json(result)
  } catch (error) {
    console.error('Error fetching usage analytics:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
