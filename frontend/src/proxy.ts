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
 * this machine and this port may call them. A loopback Host stops DNS rebinding,
 * where a foreign page sends a matching Origin and Host.
 */
export function proxy(request: NextRequest) {
  const hostHeader = request.headers.get("host") ?? "";
  const host = parseHost(hostHeader);
  if (!host || !LOOPBACK.has(host.hostname)) {
    return new NextResponse("Forbidden: Host must be loopback", { status: 403 });
  }

  const origin = request.headers.get("origin");
  // Browsers always send Origin on a same-origin POST or DELETE. A write without
  // it comes from a script or another local process, not from this page.
  if (origin === null && request.method !== "GET" && request.method !== "HEAD") {
    return new NextResponse("Forbidden: Origin required for writes", { status: 403 });
  }
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
