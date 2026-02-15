import { withAuth } from 'next-auth/middleware'

// Next.js 15+ uses proxy.ts; expose a named proxy function instead of middleware
export const proxy = withAuth({
  callbacks: {
    authorized: ({ token }) => !!token,
  },
})

export const config = {
  matcher: ['/dashboard/:path*', '/api/keys/:path*', '/api/rules/:path*', '/api/analytics/:path*'],
}
