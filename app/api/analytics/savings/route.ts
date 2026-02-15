import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { prisma } from '@/lib/prisma'

// GET /api/analytics/savings - Cost savings statistics
export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions)

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { searchParams } = new URL(request.url)
    const period = searchParams.get('period') || '30d'

    // Calculate date range
    const daysMap: Record<string, number> = {
      '7d': 7,
      '30d': 30,
      '90d': 90,
    }
    const days = daysMap[period] || 30
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - days)

    // Aggregate cost data
    const result = await prisma.usageRecord.aggregate({
      where: {
        userId: session.user.id,
        timestamp: {
          gte: startDate,
        },
        success: true,
      },
      _sum: {
        originalCost: true,
        optimizedCost: true,
        costSaved: true,
      },
    })

    const totalOriginalCost = result._sum.originalCost || 0
    const totalOptimizedCost = result._sum.optimizedCost || 0
    const totalSaved = result._sum.costSaved || 0
    const savingsPercentage = totalOriginalCost > 0
      ? (totalSaved / totalOriginalCost) * 100
      : 0

    return NextResponse.json({
      totalOriginalCost,
      totalOptimizedCost,
      totalSaved,
      savingsPercentage,
    })
  } catch (error) {
    console.error('Error fetching savings analytics:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
