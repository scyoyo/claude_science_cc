/**
 * Catch-all API proxy: forwards /api/* requests to the backend.
 *
 * Next.js rewrites don't reliably proxy external URLs in production/standalone
 * mode (they 307-redirect instead). This route handler does a proper server-side
 * fetch and returns the response — no redirect, guaranteed to work.
 */

export const dynamic = "force-dynamic";

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
  // Forward Accept header (needed for SSE: text/event-stream)
  const accept = req.headers.get("accept");
  if (accept) headers["Accept"] = accept;
  // Forward client IP so backend rate limiter can identify real users
  const xff = req.headers.get("x-forwarded-for");
  if (xff) headers["X-Forwarded-For"] = xff;

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

  // SSE: pipe body through TransformStream to force chunk-by-chunk forwarding
  // (prevents Node.js / Next.js runtime from buffering the entire response)
  const isSSE = resCt?.includes("text/event-stream");
  if (isSSE && res.body) {
    responseHeaders.set("Cache-Control", "no-cache, no-transform");
    responseHeaders.set("X-Accel-Buffering", "no");
    responseHeaders.set("Connection", "keep-alive");
    responseHeaders.set("Content-Encoding", "identity");

    // Pipe through a passthrough TransformStream so each chunk flushes immediately
    const { readable, writable } = new TransformStream();
    res.body.pipeTo(writable).catch(() => {});

    return new Response(readable, {
      status: res.status,
      headers: responseHeaders,
    });
  }

  // Non-SSE: forward caching / buffering headers from backend
  const resCc = res.headers.get("cache-control");
  if (resCc) responseHeaders.set("Cache-Control", resCc);
  const resXab = res.headers.get("x-accel-buffering");
  if (resXab) responseHeaders.set("X-Accel-Buffering", resXab);

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
