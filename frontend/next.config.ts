import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  turbopack: {
    root: frontendRoot,
  },
  // The dev badge sits bottom-left, exactly where the stage's task rail lives.
  devIndicators: false,
  // The sandbox preview is served from a proxied origin (*.e2b.app), and local
  // probes hit 127.0.0.1 rather than localhost. Without this the dev server
  // refuses the client chunks and the page never hydrates.
  allowedDevOrigins: ["localhost", "127.0.0.1", "*.e2b.app"],
};

export default nextConfig;
