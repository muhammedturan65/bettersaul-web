import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const PUBLIC_PATHS = ['/login', '/register', '/api/auth']
const ADMIN_PATHS = ['/admin']

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  // Allow static files and Next internals
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname === '/' ||
    pathname.match(/\.(svg|png|jpg|jpeg|gif|webp|ico|css|js|map)$/)
  ) {
    return NextResponse.next()
  }

  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET })

  // Protected API routes (except /api/auth and /api/public)
  if (pathname.startsWith('/api/')) {
    if (!token) {
      return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
    }
    // Admin-only API routes
    if (pathname.startsWith('/api/admin') && token.role !== 'admin') {
      return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
    }
    return NextResponse.next()
  }

  // For non-API, non-public routes — require auth
  if (!token) {
    const loginUrl = new URL('/login', req.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Admin pages
  if (ADMIN_PATHS.some((p) => pathname.startsWith(p)) && token.role !== 'admin') {
    return NextResponse.redirect(new URL('/', req.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
