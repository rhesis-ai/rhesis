# First stage: Build the application
FROM node:22-alpine AS builder

# Add build dependencies
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy package files first to leverage Docker cache
COPY src/package.json src/package-lock.json ./

# Install all dependencies (including devDependencies for build tools)
# Note: Removed cache mount to avoid corruption in CI environments
RUN npm ci --prefer-offline --no-audit

# Copy source files needed for build
COPY src/next.config.mjs src/mdx-components.js src/theme.config.jsx ./
COPY src/public ./public
COPY src/app ./app
COPY src/components ./components
COPY content ./content
COPY src/styles ./styles

# Set build environment variables
ENV NEXT_TELEMETRY_DISABLED=1

# Build the Next.js application (this will also run postbuild with pagefind)
RUN npm run build

# Second stage: Production runtime
FROM node:22-alpine AS runner

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
COPY src/package.json src/package-lock.json ./

# Install only production dependencies
# Note: Removed cache mount to avoid corruption in CI environments
RUN npm ci --only=production --prefer-offline --no-audit && \
    npm cache clean --force && \
    rm -rf /tmp/*

# Copy built application from builder stage
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/content ./content
COPY --from=builder --chown=nextjs:nodejs /app/styles ./styles
COPY --from=builder --chown=nextjs:nodejs /app/next.config.mjs ./
COPY --from=builder --chown=nextjs:nodejs /app/mdx-components.js ./
COPY --from=builder --chown=nextjs:nodejs /app/theme.config.jsx ./

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3001

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
  CMD curl -f http://localhost:3001/ || exit 1

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]

# Start the application
CMD ["npm", "start"]
