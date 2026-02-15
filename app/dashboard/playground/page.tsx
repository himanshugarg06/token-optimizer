import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/auth-config'
import { prisma } from '@/lib/prisma'
import { redirect } from 'next/navigation'
import PlaygroundClient from './playground-client'

export default async function PlaygroundPage() {
  const session = await getServerSession(authOptions)

  if (!session?.user?.id) {
    redirect('/auth/signin')
  }

  // Fetch user's API keys
  const apiKeys = await prisma.apiKey.findMany({
    where: {
      userId: session.user.id,
      isActive: true,
    },
    select: {
      id: true,
      name: true,
      keyPrefix: true,
    },
    orderBy: {
      createdAt: 'desc',
    },
  })

  return (
    <div className="min-h-screen bg-black p-6">
      <div className="mb-5">
        <h1 className="text-2xl font-medium text-white">Optimization Playground</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Test the token optimizer and see the magic happen in real-time
        </p>
      </div>

      <PlaygroundClient
        userId={session.user.id}
        userEmail={session.user.email || ''}
        apiKeys={apiKeys}
      />
    </div>
  )
}
