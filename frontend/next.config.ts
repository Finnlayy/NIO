import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Dauerbetrieb baut jede Version in einen eigenen Ordner (deploy/release_apollo.sh)
  // und schaltet nur den Zeiger um. Ohne die Variable bleibt alles bei .next.
  distDir: process.env.NIO_NEXT_DIST_DIR || ".next",
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
