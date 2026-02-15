export { default } from 'next-auth/middleware'

export const config = {
  matcher: ['/dashboard/:path*', '/api/keys/:path*', '/api/rules/:path*', '/api/analytics/:path*']
}
