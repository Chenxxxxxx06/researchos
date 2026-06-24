import { NextResponse, type NextRequest } from 'next/server';

/**
 * UX guard only — NOT real authentication. It checks for the presence of the
 * session cookie to avoid flashing protected pages. Actual authorization is
 * enforced by the backend on every API call (and via GET /auth/me).
 */
const SESSION_COOKIE = 'ros_session';

const PROTECTED_PREFIXES = ['/projects'];
const AUTH_PAGES = ['/login', '/register'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p));
  const isAuthPage = AUTH_PAGES.includes(pathname);

  if (isProtected && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

  if (isAuthPage && hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = '/projects';
    url.search = '';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/projects/:path*', '/login', '/register'],
};
