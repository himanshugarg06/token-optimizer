import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { prisma } from '@/lib/prisma'

// GET /api/analytics/recent - Recent API calls log
export async function GET(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions)

    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { searchParams } = new URL(request.url)
    const limit = parseInt(searchParams.get('limit') || '50', 10)
    const offset = parseInt(searchParams.get('offset') || '0', 10)

    // Fetch recent usage records
    const records = await prisma.usageRecord.findMany({
      where: {
        userId: session.user.id,
      },
      orderBy: {
        timestamp: 'desc',
      },
      take: limit,
      skip: offset,
      include: {
        apiKey: {
          select: {
            name: true,
            keyPrefix: true,
          },
        },
      },
    })

    // Get total count for pagination
    const total = await prisma.usageRecord.count({
      where: {
        userId: session.user.id,
      },
    })

    return NextResponse.json({
      records,
      pagination: {
        total,
        limit,
        offset,
        hasMore: offset + limit < total,
      },
    })
  } catch (error) {
    console.error('Error fetching recent records:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
