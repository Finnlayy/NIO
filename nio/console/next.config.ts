import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output standalone for Docker deployment on Cloud Run
  output: "standalone",

  // GenKit is CommonJS and pulls native OpenTelemetry modules; keep them out of
  // the client bundle and out of Turbopack's resolver so server routes can import them.
  serverExternalPackages: [
    "genkit",
    "@genkit-ai/ai",
    "@genkit-ai/core",
    "@genkit-ai/vertexai",
    "@genkit-ai/google-cloud",
  ],
  
  // Optimize for production
  poweredByHeader: false,
  compress: true,
  
  // Image optimization for Cloud Run
  images: {
    unoptimized: process.env.NODE_ENV === "production",
    formats: ["image/avif", "image/webp"],
  },
  
  // Security headers
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "X-DNS-Prefetch-Control",
            value: "on",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            key: "X-Frame-Options",
            value: "SAMEORIGIN",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
        ],
      },
    ];
  },
  
  // Environment variables validation
  env: {
    PROJECT_ID: process.env.PROJECT_ID || "",
    VERTEX_AI_LOCATION: process.env.VERTEX_AI_LOCATION || "europe-west3",
    NIO_API_URL: process.env.NIO_API_URL || "http://localhost:4000",
  },

  async rewrites() {
    const apiUrl = process.env.NIO_API_URL ?? "http://localhost:4000";
    return [{ source: "/nio-api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
