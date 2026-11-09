import { NextResponse, type NextRequest } from "next/server";

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** Parses a Host value; anything that is more than host and port comes back null. */
function parseHost(value: string): URL | null {
  try {
    const url = new URL(`http://${value}`);
    return url.host === value.toLowerCase() ? url : null;
  } catch {
    return null;
  }
}

/**
 * Guard for /api/*: the routes hold keys and start processes, so only pages from
 * this machine and this port may call them. A loopback Host (or an explicitly
 * configured preview host) stops DNS rebinding with matching Origin and Host.
 */
export function proxy(request: NextRequest) {
  const hostHeader = request.headers.get("host") ?? "";
  const host = parseHost(hostHeader);
  const previewHost = process.env.NIO_PREVIEW_HOST;
  const allowedPreview = previewHost ? parseHost(previewHost) : null;
  if (!host || (!LOOPBACK.has(host.hostname) && host.host !== allowedPreview?.host)) {
    return new NextResponse("Forbidden: Host must be loopback or the configured preview host", { status: 403 });
  }

  const origin = request.headers.get("origin");
  if (origin !== null) {
    let originHost = "";
    try {
      originHost = new URL(origin).host;
    } catch {
      // Falls through to the refusal: `null` origins and garbage are not this page.
    }
    if (originHost !== host.host) {
      return new NextResponse("Forbidden: Cross-origin API request", { status: 403 });
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};
