FROM mirror.gcr.io/library/node:24-alpine AS base

########################################################
# First stage: Install dependencies
#
# Build context is the repo root so the file: link
# "file:../../ee/frontend" in apps/frontend/package.json
# can be resolved during npm ci.
########################################################

FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy only the files npm needs to resolve the file: link and install.
# ee/frontend/package.json is required so npm recognises @rhesis/ee-frontend.
COPY ee/frontend/package.json ./ee/frontend/package.json
COPY apps/frontend/package.json apps/frontend/package-lock.json ./apps/frontend/
# patches/ must be present before `npm ci` because the postinstall script runs
# patch-package, which looks for ./patches/ relative to the working directory.
# Without it the MUI SSR fix is silently skipped in every Docker build.
COPY apps/frontend/patches ./apps/frontend/patches

RUN cd apps/frontend && npm ci --legacy-peer-deps

########################################################
# Second stage: Build the application
########################################################

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/apps/frontend/node_modules ./apps/frontend/node_modules

# Copy source files that the build needs.
COPY apps/frontend/tsconfig.json apps/frontend/next.config.mjs apps/frontend/eslint.config.mjs \
     apps/frontend/package.json apps/frontend/package-lock.json ./apps/frontend/
COPY apps/frontend/public ./apps/frontend/public
COPY apps/frontend/src ./apps/frontend/src
COPY apps/frontend/scripts ./apps/frontend/scripts

# EE source must be present so transpilePackages can compile it.
COPY ee/frontend/package.json ./ee/frontend/package.json
COPY ee/frontend/src ./ee/frontend/src

# Remove ALL .env files to ensure they don't override container env vars
RUN find . -name ".env*" -type f -delete

# Define ARG for this stage. Default to production if not set.
ARG FRONTEND_ENV=production

# Git metadata injected by CI pipeline (NEXT_PUBLIC_ prefix for client-side access)
ARG GIT_BRANCH
ARG GIT_COMMIT
ENV GIT_BRANCH=${GIT_BRANCH}
ENV GIT_COMMIT=${GIT_COMMIT}
ENV NEXT_PUBLIC_GIT_BRANCH=${GIT_BRANCH}
ENV NEXT_PUBLIC_GIT_COMMIT=${GIT_COMMIT}

# NEXT_PUBLIC_API_BASE_URL and NEXT_PUBLIC_QUICK_START are fixed placeholders;
# replace-runtime-env.sh substitutes the real values at container start.

# Create a temporary .env file using build arguments for NEXT_PUBLIC_ and direct placeholders for the rest
RUN echo "NEXTAUTH_SECRET=temporary-build-secret-not-for-production" > apps/frontend/.env && \
    echo "NEXT_PUBLIC_API_BASE_URL=__NEXT_PUBLIC_API_BASE_URL__" >> apps/frontend/.env && \
    echo "BACKEND_URL=${BACKEND_URL}" >> apps/frontend/.env && \
    echo "NEXT_PUBLIC_QUICK_START=__NEXT_PUBLIC_QUICK_START__" >> apps/frontend/.env && \
    echo "GOOGLE_CLIENT_ID=placeholder-client-id" >> apps/frontend/.env && \
    echo "GOOGLE_CLIENT_SECRET=placeholder-client-secret" >> apps/frontend/.env && \
    echo "AUTH_SECRET=placeholder-auth-secret" >> apps/frontend/.env

# Set environment variables for better Next.js performance
ENV NEXT_TELEMETRY_DISABLED=1
ENV FRONTEND_ENV=${FRONTEND_ENV}
# Give the webpack worker enough heap. next.config.mjs sets this via
# process.env.NODE_OPTIONS but that only propagates to child processes;
# setting it here ensures the primary webpack process respects the limit too.
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Print the FRONTEND_ENV value for debugging
RUN echo "FRONTEND_ENV value is: '${FRONTEND_ENV}'"

# Build the Next.js application from the apps/frontend subdirectory
RUN if [ "$FRONTEND_ENV" = "production" ] || [ "$FRONTEND_ENV" = "staging" ] || [ "$FRONTEND_ENV" = "development" ] || [ "$FRONTEND_ENV" = "local" ]; then \
        cd apps/frontend && npm run build; \
    else \
        echo "Skipping build for non-production environment"; \
        mkdir -p apps/frontend/.next; \
    fi

# Remove the temporary .env file
RUN rm -f apps/frontend/.env

########################################################
# Third stage: Run the application
########################################################
FROM base AS runner

# Redefine ARG for this stage
ARG FRONTEND_ENV=production

# Add runtime dependencies
RUN apk add --no-cache curl

WORKDIR /app

# Set environment variables
ENV FRONTEND_ENV=${FRONTEND_ENV}
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user and switch to it
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs && \
    chown -R nextjs:nodejs /app

# The standalone output mirrors the repo-root structure because
# outputFileTracingRoot is set to the repo root in next.config.mjs.
# standalone/ contains apps/frontend/server.js (and ee/frontend/ if traced).
COPY --from=builder /app/apps/frontend/.next/standalone ./

# Static assets and public must sit alongside server.js so Next.js serves them.
COPY --from=builder --chown=nextjs:nodejs /app/apps/frontend/.next/static ./apps/frontend/.next/static
COPY --from=builder /app/apps/frontend/public ./apps/frontend/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/frontend/scripts/replace-runtime-env.sh ./apps/frontend/scripts/replace-runtime-env.sh
RUN chmod +x /app/apps/frontend/scripts/replace-runtime-env.sh

# Do NOT copy src, tsconfig.json, eslint.config.mjs or any .env files to production image
# Install dependencies and handle environment-specific setup
RUN if [ "$FRONTEND_ENV" = "production" ] || [ "$FRONTEND_ENV" = "staging" ] || [ "$FRONTEND_ENV" = "development" ] || [ "$FRONTEND_ENV" = "local" ]; then \
        echo "Production mode detected"; \
    else \
        echo "Development mode detected"; \
        echo "Source files kept for development mode"; \
        npm ci --legacy-peer-deps && npm cache clean --force; \
    fi

USER nextjs

# EXPOSE uses the default port, but runtime PORT env var will override this
EXPOSE 3000

# Add a health check that uses the PORT env var with fallback
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/ || exit 1

ENTRYPOINT ["/app/apps/frontend/scripts/replace-runtime-env.sh"]

# server.js does process.chdir(__dirname) so PORT env var drives the port.
# Run from /app; server.js is at apps/frontend/server.js inside the standalone output.
CMD ["sh", "-c", "export PORT=${PORT:-3000} && if [ \"$FRONTEND_ENV\" = \"production\" ] || [ \"$FRONTEND_ENV\" = \"staging\" ] || [ \"$FRONTEND_ENV\" = \"development\" ] || [ \"$FRONTEND_ENV\" = \"local\" ]; then node apps/frontend/server.js; else cd apps/frontend && npm run dev; fi"]
