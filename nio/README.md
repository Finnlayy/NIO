# NIO Platform

Full-stack monorepo merging [Finnlayy/NIO](https://github.com/Finnlayy/NIO) middleware with the Orchestrator Console UI, wired to [`twin/model-manifest.json`](../twin/model-manifest.json).

## Structure

```
nio/
  backend/     # NIO middleware (port 4000)
  console/     # Next.js UI + Genkit/memory APIs (port 3000)
  shared/      # Manifest schema + types
```

## Quick start

```bash
# From D:\General\nio
cp .env.example .env

# Start PostgreSQL
npm run db:up

# Push Drizzle schema
npm run db:migrate

# Install (if not done)
npm install

# Run backend + console
npm run dev
```

- Console: http://localhost:3000
- NIO API: http://localhost:4000
- Manifest: http://localhost:4000/api/models/manifest

## API endpoints

| Route | Description |
|-------|-------------|
| `GET /health` | Health check |
| `GET /api/models/manifest` | Full model manifest |
| `GET /api/models/resolve?role=worker` | Resolve role to tier/model |
| `GET /api/telemetry` | Recent telemetry events |
| `GET /api/agents/registry` | Agent registry with manifest tiers |
| `POST /api/task` | Execute task through NIO middleware |

## Build

```bash
npm run build
```
