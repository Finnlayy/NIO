# =============================================================================
# NEXUS — Google Cloud Agent Operations
# Multi-stage Dockerfile for Cloud Run (Next.js 16)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Dependencies
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# -----------------------------------------------------------------------------
# Stage 2: Builder
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

# Build arguments for environment-specific configuration
ARG DATABASE_URL
ARG PROJECT_ID
ARG VERTEX_AI_LOCATION

ENV DATABASE_URL=$DATABASE_URL
ENV PROJECT_ID=$PROJECT_ID
ENV VERTEX_AI_LOCATION=$VERTEX_AI_LOCATION

# Build Next.js application
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 3: Runner (Production)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Set environment variables
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Install curl for health checks
RUN apk add --no-cache curl

# Copy necessary files from builder
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Set correct permissions
RUN chown -R nextjs:nodejs /app

USER nextjs

# Expose port Cloud Run expects
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Start Next.js server
CMD ["node", "server.js"]

# -----------------------------------------------------------------------------
# Labels for Google Cloud
# -----------------------------------------------------------------------------
LABEL maintainer="Nexus Team"
LABEL description="Nexus Console - Google Cloud Agent Operations"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/nexus/nexus-console"
