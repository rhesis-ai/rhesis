# First stage: Build the application
FROM node:22-alpine AS base

########################################################
# First stage: Install dependencies
########################################################

FROM base AS deps

# Add build dependencies
RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY src/package.json src/package-lock.json ./

RUN npm ci --prefer-offline --no-audit

########################################################
# Second stage: Build the application
########################################################
FROM base AS builder
WORKDIR /app


COPY --from=deps /app/node_modules ./node_modules

# Copy source files needed for build
COPY src/package.json src/package-lock.json src/next.config.mjs src/mdx-components.js src/theme.config.jsx ./
COPY src/public ./public
COPY src/app ./app
COPY src/components ./components
COPY src/lib ./lib
COPY content ./content
COPY src/styles ./styles

# Set build environment variables
ENV NEXT_TELEMETRY_DISABLED=1

# Build the Next.js application (this will also run postbuild with pagefind)
RUN npm run build

########################################################
# Third stage: Production runtime
########################################################

FROM base AS runner

# Add only runtime dependencies
RUN apk add --no-cache curl dumb-init

WORKDIR /app

# Set production environment variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV FRONTEND_ENV=production

# Create non-root user first
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy package files
COPY src/package.json src/package-lock.json src/next.config.mjs src/mdx-components.js src/theme.config.jsx ./

COPY --from=builder  /app/public ./public

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone/app ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Copy built application from builder stage
COPY --from=builder --chown=nextjs:nodejs /app/content ./content
COPY --from=builder --chown=nextjs:nodejs /app/lib ./lib
COPY --from=builder --chown=nextjs:nodejs /app/styles ./styles

# Switch to non-root user
USER nextjs

# Expose port
ENV PORT=3001
EXPOSE 3001

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
  CMD curl -f http://localhost:3001/ || exit 1

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]

# Start the application
CMD ["node", "server.js"]
