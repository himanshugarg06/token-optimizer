import { withAuth } from 'next-auth/middleware'

// Next.js 15+ uses proxy.ts; expose a named proxy function instead of middleware
export const proxy = withAuth({
  callbacks: {
    authorized: ({ token }) => !!token,
  },
})

export const config = {
  // Exclude /api/keys/validate so backend validation can call it without NextAuth
  matcher: [
    '/dashboard/:path*',
    '/api/keys/:path((?!validate).*)',
    '/api/rules/:path*',
    '/api/analytics/:path*',
    // Protect future /api/v1 routes but leave events/config open for backend ingestion
    '/api/v1/:path((?!events)(?!config).*)',
  ],
}
