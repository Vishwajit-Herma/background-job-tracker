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
  
  // UX route guard: if no session cookie, redirect to /login
  // NOTE: This is UX-only. Django must STILL protect the API!
  if (!sessionId && !isAuthRoute && !url.pathname.startsWith("/_next") && !url.pathname.startsWith("/api")) {
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // Optional: Redirect logged-in users away from /login back to dashboard
  if (sessionId && isAuthRoute) {
    url.pathname = "/projects"; // Or wherever the default dashboard is
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
