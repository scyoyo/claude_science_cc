import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

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
