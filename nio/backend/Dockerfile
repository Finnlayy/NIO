# =============================================================================
# NIO Neural Orchestrator — Cloud Run Dockerfile
# Build context: nio/ (monorepo root)
# =============================================================================

FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY package.json package-lock.json ./
COPY backend/package.json ./backend/
COPY shared/package.json ./shared/

RUN npm ci --workspace=backend --workspace=shared --include-workspace-root

FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY backend ./backend
COPY shared ./shared
COPY twin ./twin

RUN npm run build --workspace=backend

FROM node:20-alpine AS runner

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 orchestrator

ENV NODE_ENV=production
ENV PORT=8080
ENV HOST=0.0.0.0
ENV MODEL_MANIFEST_PATH=/app/twin/model-manifest.json

RUN apk add --no-cache curl

COPY --from=builder /app/backend/dist ./backend/dist
COPY --from=builder /app/backend/package.json ./backend/package.json
COPY --from=builder /app/backend/prompts ./backend/prompts
COPY --from=builder /app/backend/agents ./backend/agents
COPY --from=builder /app/twin ./twin
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package.json ./package.json
COPY --from=deps /app/backend/node_modules ./backend/node_modules
COPY --from=deps /app/shared ./shared

WORKDIR /app/backend

RUN chown -R orchestrator:nodejs /app

USER orchestrator

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["node", "dist/backend/src/server.js"]

LABEL maintainer="NIO Team"
LABEL description="Neural Orchestrator API — manifest-driven LLM middleware"
LABEL version="1.0.0"
