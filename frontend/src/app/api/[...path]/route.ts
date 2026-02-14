/**
 * Catch-all API proxy: forwards /api/* requests to the backend.
 *
 * Next.js rewrites don't reliably proxy external URLs in production/standalone
 * mode (they 307-redirect instead). This route handler does a proper server-side
 * fetch and returns the response — no redirect, guaranteed to work.
 */

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

async function proxy(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const url = new URL(req.url);
  const target = `${BACKEND}/api/${path.join("/")}${url.search}`;

  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["Content-Type"] = ct;
  const auth = req.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;

  // Read body once as Blob so it can be re-sent on 307/308 redirects
  // (raw ArrayBuffer gets detached after the first fetch attempt)
  let body: Blob | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = new Blob([await req.arrayBuffer()]);
  }

  // Use manual redirect to avoid "detached ArrayBuffer" crash on 307/308
  let res = await fetch(target, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
  });

  // Follow redirects manually (FastAPI trailing-slash 307s)
  if (res.status === 307 || res.status === 308) {
    const location = res.headers.get("location");
    if (location) {
      const redirectUrl = location.startsWith("http") ? location : `${BACKEND}${location}`;
      res = await fetch(redirectUrl, {
        method: req.method,
        headers,
        body,
        redirect: "manual",
      });
    }
  }

  // Forward response headers
  const responseHeaders = new Headers();
  const resCt = res.headers.get("content-type");
  if (resCt) responseHeaders.set("Content-Type", resCt);
  const resCd = res.headers.get("content-disposition");
  if (resCd) responseHeaders.set("Content-Disposition", resCd);

  return new Response(res.body, {
    status: res.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
export const PATCH = proxy;
