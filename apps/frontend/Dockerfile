# First stage: Build the application
FROM node:22-alpine AS builder

# Add build dependencies
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Define build arguments only for NEXT_PUBLIC_ variables
ARG NEXT_PUBLIC_API_BASE_URL=https://api.rhesis.ai
ARG NEXT_PUBLIC_APP_URL=https://app.rhesis.ai
ARG NEXT_PUBLIC_AUTH0_DOMAIN=auth.rhesis.ai
ARG NEXT_PUBLIC_AUTH0_CLIENT_ID=placeholder-auth0-client-id

# Copy package.json and package-lock.json first to leverage Docker cache
COPY package.json package-lock.json ./

# Install dependencies with cache mounting for faster builds
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy only necessary files for the build
COPY tsconfig.json next.config.mjs .eslintrc.json ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts

# Remove ALL .env files to ensure they don't override container env vars
RUN find . -name ".env*" -type f -delete

# Create a temporary .env file using build arguments for NEXT_PUBLIC_ and direct placeholders for the rest
RUN echo "NEXTAUTH_SECRET=temporary-build-secret-not-for-production" > .env && \
    echo "NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}" >> .env && \
    echo "NEXT_PUBLIC_APP_URL=${NEXT_PUBLIC_APP_URL}" >> .env && \
    echo "NEXT_PUBLIC_AUTH0_DOMAIN=${NEXT_PUBLIC_AUTH0_DOMAIN}" >> .env && \
    echo "NEXT_PUBLIC_AUTH0_CLIENT_ID=${NEXT_PUBLIC_AUTH0_CLIENT_ID}" >> .env && \
    echo "GOOGLE_CLIENT_ID=placeholder-client-id" >> .env && \
    echo "GOOGLE_CLIENT_SECRET=placeholder-client-secret" >> .env && \
    echo "AUTH_SECRET=placeholder-auth-secret" >> .env

# Set environment variables for better Next.js performance
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=development

# For development mode, we'll start the dev server directly
# Remove the temporary .env file
RUN rm -f .env

# Second stage: Run the application
FROM node:22-alpine AS runner

# Add runtime dependencies
RUN apk add --no-cache curl

WORKDIR /app

# Set environment variables
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Copy all necessary files from the builder stage
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./
COPY --from=builder /app/src ./src
COPY --from=builder /app/tsconfig.json ./
COPY --from=builder /app/.eslintrc.json ./
# Do NOT copy any .env files to production image

# Install all dependencies for development
RUN npm ci && npm cache clean --force

# Create a non-root user and switch to it
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs && \
    chown -R nextjs:nodejs /app
USER nextjs

# EXPOSE uses the default port, but runtime PORT env var will override this
EXPOSE 3000

# Add a health check that uses the PORT env var with fallback
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/ || exit 1

# Start the development server with PORT defaulting to 3000 if not set
CMD ["sh", "-c", "export PORT=${PORT:-3000} && npm run dev"]
