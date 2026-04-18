import { withSentryConfig } from '@sentry/nextjs'

/** @type {import('next').NextConfig} */
const apiOrigin = (process.env.NEXT_PUBLIC_API_ORIGIN ?? 'http://localhost:8000').replace(/\/$/, '')

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${apiOrigin}/api/:path*` },
      { source: '/billing/:path*', destination: `${apiOrigin}/billing/:path*` },
      { source: '/invitations/:path*', destination: `${apiOrigin}/invitations/:path*` },
      { source: '/static/:path*', destination: `${apiOrigin}/static/:path*` },
    ]
  },
}

export default withSentryConfig(nextConfig, {
  silent: true,
  disableLogger: true,
})
