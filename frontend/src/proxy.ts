import createMiddleware from "next-intl/middleware";
import type { NextRequest } from "next/server";
import { routing } from "./i18n/routing";

const intlMiddleware = createMiddleware(routing);

export function proxy(request: NextRequest) {
  return intlMiddleware(request);
}

export const config = {
  matcher: [
    // Match all pathnames except:
    // - /api (backend proxy)
    // - /ws (websocket proxy)
    // - /_next (Next.js internals)
    // - /favicon.ico, /icons, etc.
    "/((?!api|ws|_next|favicon.ico|.*\\.).*)",
  ],
};
