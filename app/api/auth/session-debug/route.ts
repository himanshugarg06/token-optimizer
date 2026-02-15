import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'

export async function GET() {
  const session = await getServerSession(authOptions)

  return NextResponse.json({
    session,
    hasSession: !!session,
    hasUser: !!session?.user,
    userId: session?.user?.id,
  })
}
