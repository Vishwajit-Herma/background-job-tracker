import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  // Extract session ID cookie (default Django session cookie name)
  const sessionId = request.cookies.get("sessionid");
  const url = request.nextUrl.clone();
  
  // Public routes (Auth flow)
  const isAuthRoute = 
    url.pathname === "/login" || 
    url.pathname === "/register" || 
    url.pathname === "/forgot-password" || 
    url.pathname.startsWith("/reset-password") ||
    url.pathname.startsWith("/verify-email");
  
  // UX route guard: if no session cookie, redirect to /login for protected routes
  // NOTE: This is UX-only. Django must STILL protect the API!
  if (!sessionId && !isAuthRoute && !url.pathname.startsWith("/_next") && !url.pathname.startsWith("/api")) {
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // Only redirect logged-in users away from login/register/forgot-password (guest-only routes)
  // NEVER redirect away from /verify-email or /reset-password!
  const isGuestOnlyRoute =
    url.pathname === "/login" ||
    url.pathname === "/register" ||
    url.pathname === "/forgot-password";

  if (sessionId && isGuestOnlyRoute) {
    url.pathname = "/projects";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Apply middleware to all routes except API, static assets, and Next internals
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
