FROM node:22-alpine AS base

########################################################
# First stage: Install dependencies
########################################################

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --legacy-peer-deps

########################################################
# Second stage: Build the application
########################################################

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules

# Copy only necessary files for the build
COPY tsconfig.json next.config.mjs .eslintrc.json package.json package-lock.json ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts

# Remove ALL .env files to ensure they don't override container env vars
RUN find . -name ".env*" -type f -delete

# Define ARG for this stage. Default to production if not set.
ARG FRONTEND_ENV=production

# Define build arguments only for NEXT_PUBLIC_ variables
ARG NEXT_PUBLIC_API_BASE_URL=https://api.rhesis.ai
ARG NEXT_PUBLIC_APP_URL=https://app.rhesis.ai
ARG NEXT_PUBLIC_AUTH0_DOMAIN=auth.rhesis.ai
ARG NEXT_PUBLIC_AUTH0_CLIENT_ID=placeholder-auth0-client-id
ARG NEXT_PUBLIC_LOCAL_AUTH_ENABLED=false

# Create a temporary .env file using build arguments for NEXT_PUBLIC_ and direct placeholders for the rest
RUN echo "NEXTAUTH_SECRET=temporary-build-secret-not-for-production" > .env && \
    echo "NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}" >> .env && \
    echo "BACKEND_URL=${BACKEND_URL}" >> .env && \
    echo "NEXT_PUBLIC_APP_URL=${NEXT_PUBLIC_APP_URL}" >> .env && \
    echo "NEXT_PUBLIC_AUTH0_DOMAIN=${NEXT_PUBLIC_AUTH0_DOMAIN}" >> .env && \
    echo "NEXT_PUBLIC_AUTH0_CLIENT_ID=${NEXT_PUBLIC_AUTH0_CLIENT_ID}" >> .env && \
    echo "NEXT_PUBLIC_LOCAL_AUTH_ENABLED=${NEXT_PUBLIC_LOCAL_AUTH_ENABLED}" >> .env && \
    echo "GOOGLE_CLIENT_ID=placeholder-client-id" >> .env && \
    echo "GOOGLE_CLIENT_SECRET=placeholder-client-secret" >> .env && \
    echo "AUTH_SECRET=placeholder-auth-secret" >> .env

# Set environment variables for better Next.js performance
ENV NEXT_TELEMETRY_DISABLED=1
ENV FRONTEND_ENV=${FRONTEND_ENV}

# Print the FRONTEND_ENV value for debugging
RUN echo "🔍 FRONTEND_ENV value is: '${FRONTEND_ENV}'"

# Build the Next.js application
#RUN npm run build
RUN if [ "$FRONTEND_ENV" = "production" ] || [ "$FRONTEND_ENV" = "staging" ] || [ "$FRONTEND_ENV" = "development" ] || [ "$FRONTEND_ENV" = "local" ]; then \
        npm run build; \
    else \
        echo "Skipping build for non-production environment"; \
        mkdir -p .next; \
    fi

# Remove the temporary .env file
RUN rm -f .env

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

COPY --from=builder  /app/public ./public
COPY --from=builder  /app/.next/standalone ./
COPY --from=builder  /app/.next/static ./.next/static

# Do NOT copy src, tsconfig.json, .eslintrc.json or any .env files to production image
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

# Start the appropriate server based on FRONTEND_ENV
CMD ["sh", "-c", "export PORT=${PORT:-3000} && if [ \"$FRONTEND_ENV\" = \"production\" ] || [ \"$FRONTEND_ENV\" = \"staging\" ] || [ \"$FRONTEND_ENV\" = \"development\" ] || [ \"$FRONTEND_ENV\" = \"local\" ]; then node server.js; else npm run dev; fi"]
