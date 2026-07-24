// Set memory limit to prevent swapping
process.env.NODE_OPTIONS = '--max-old-space-size=4096';

import path from 'path';
import { fileURLToPath } from 'url';
import { readFileSync } from 'fs';
import { execSync } from 'child_process';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Get git info from CI-injected env vars first, fall back to git commands (local dev)
function getGitInfo() {
  if (process.env.GIT_BRANCH || process.env.GIT_COMMIT) {
    return { branch: process.env.GIT_BRANCH, commit: process.env.GIT_COMMIT };
  }
  try {
    const branch = execSync('git rev-parse --abbrev-ref HEAD', {
      encoding: 'utf8',
      timeout: 5000,
    }).trim();
    const commit = execSync('git rev-parse --short HEAD', {
      encoding: 'utf8',
      timeout: 5000,
    }).trim();
    return { branch, commit };
  } catch (error) {
    console.warn('Could not get git information:', error.message);
    return { branch: undefined, commit: undefined };
  }
}

const isDev = process.env.FRONTEND_ENV === 'development';
const isProd = process.env.FRONTEND_ENV === 'production';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // ===== DEVELOPMENT-SPECIFIC ANTI-CACHING =====
  // These are the key additions to fix your caching issues
  generateEtags: !isDev, // Disable ETags in development

  // Standalone mode for minimizing container size
  output: 'standalone',

  // Isolated build dir for Playwright (E2E_NO_DOCKER) so a second dev server
  // can run alongside the normal dev server on port 3000.
  ...(process.env.E2E_NO_DOCKER === '1' ? { distDir: '.next-e2e' } : {}),

  // Compiler optimizations
  compiler: {
    // Remove console.log in production only
    removeConsole: isProd,
  },

  // Source maps: enable in prod for debugging, faster option in dev
  productionBrowserSourceMaps: isProd,

  // Next.js already modularizes the app's own barrel imports for the heavy
  // libraries (@mui/material, @mui/icons-material, lucide-react, date-fns,
  // recharts, …) via its default optimizePackageImports list. But that default
  // does NOT reach the barrel imports inside our transpilePackages workspace
  // package @rhesis/ee-frontend, so its `import { X } from '@mui/material'`
  // still pulls in the full CJS barrel. Under Turbopack that barrel eagerly
  // evaluates @mui/material/useMediaQuery, whose CJS→ESM interop of
  // `unstable_createUseMediaQuery` breaks in MUI v7.3.x — crashing the whole
  // app at module-eval time (see mui/material-ui#46688). Listing the packages
  // explicitly forces the barrel-to-deep-import rewrite for the transpiled EE
  // sources too, sidestepping the eager useMediaQuery evaluation.
  experimental: {
    optimizePackageImports: ['@mui/material', '@mui/icons-material'],
  },

  // Environment variables available to the client
  // NEXT_PUBLIC_ prefix guarantees availability in client components
  env: (() => {
    const gitInfo = getGitInfo();
    return {
      APP_VERSION: JSON.parse(
        readFileSync(path.join(__dirname, 'package.json'), 'utf8')
      ).version,
      NEXT_PUBLIC_FRONTEND_ENV: process.env.FRONTEND_ENV,
      NEXT_PUBLIC_GIT_BRANCH: gitInfo.branch,
      NEXT_PUBLIC_GIT_COMMIT: gitInfo.commit,
    };
  })(),

  // API routing: all /api/* requests are handled by Route Handlers under
  // src/app/api/ (see src/app/api/[...path]/route.ts for the catch-all
  // proxy and src/utils/backend-proxy.ts for the shared logic). Route
  // Handlers resolve BACKEND_URL at request time via getServerBackendUrl(),
  // so one Docker image works across all environments without build args.
  //
  // DO NOT add rewrites() for /api/* paths — rewrite destinations are baked
  // into .next/routes-manifest.json at build time and cannot be overridden
  // by runtime environment variables.

  // Development-specific: configure on-demand entries to reduce caching
  ...(isDev && {
    onDemandEntries: {
      // Shorter period to keep pages in buffer
      maxInactiveAge: 15 * 1000, // 15 seconds instead of default 60
      // Fewer pages kept simultaneously
      pagesBufferLength: 2,
    },
  }),

  // @rhesis/ee-frontend is a TypeScript package linked via a file: dependency
  // (symlink in node_modules/@rhesis/ee-frontend → ee/frontend/).
  // transpilePackages tells Next.js to compile its TypeScript source through
  // its own pipeline. webpack's resolve.symlinks=false (set below) makes
  // webpack treat the symlinked package as if its files were physically inside
  // apps/frontend/node_modules, so MUI/React resolve via normal walk-up —
  // no aliases needed.
  // next-auth ships ESM-only (no CJS build, no "require" export condition),
  // so Jest's default node_modules-are-untransformed rule leaves its
  // `import`/`export` syntax unparsed for any test that imports it without
  // mocking it out. next/jest derives its transform-ignore allowlist from
  // this array (see next/dist/build/jest/jest.js), so it must be listed
  // here, not in jest.config.js's transformIgnorePatterns — that option can
  // only add more exclusions, never un-ignore what this array controls.
  transpilePackages: ['@rhesis/ee-frontend', 'next-auth', '@auth/core'],

  // embedding-atlas pulls in Mosaic/DuckDB WASM; keep it off the server bundle.
  // Do not also list these in transpilePackages — Turbopack rejects that conflict.
  serverExternalPackages: [
    'embedding-atlas',
    '@uwdata/mosaic-core',
    '@uwdata/mosaic-spec',
    '@uwdata/mosaic-sql',
    '@uwdata/vgplot',
  ],

  // Turbopack configuration (development only — prod build uses webpack via
  // the --webpack flag in the build script).
  // root must be the repo root so Turbopack watches and resolves files inside
  // ee/frontend/ (which is physically outside apps/frontend/ but linked via
  // node_modules/@rhesis/ee-frontend). Without it, Turbopack treats
  // apps/frontend/ as the boundary and cannot process EE source files.
  turbopack: {
    root: path.resolve(__dirname, '../..'),
    resolveAlias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // Widen the standalone output trace root so Next.js includes ee/frontend/
  // files (reached through the node_modules symlink) in the standalone build.
  outputFileTracingRoot: path.resolve(__dirname, '../..'),

  // Image optimization settings
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.googleusercontent.com',
        pathname: '**',
      },
    ],
    // Keep unoptimized in development, optimize in production
    unoptimized: isDev,
    formats: ['image/webp'],
  },

  // Webpack configuration (used by both `next dev --webpack` fallback and
  // `next build --webpack` for production).
  webpack: (config, { dev, isServer }) => {
    // Next sets module.generator.asset.filename globally; that breaks asset/inline
    // (e.g. embedding-atlas inlines DuckDB WASM via new URL(data:application/wasm,...)).
    if (config.module?.generator?.asset?.filename) {
      config.module.generator['asset/resource'] = {
        filename: config.module.generator.asset.filename,
      };
      delete config.module.generator.asset;
    }

    config.module.rules.push({
      test: /\.md$/,
      type: 'asset/source',
    });

    // Resolve symlinks to their real paths during module resolution.
    // Setting this to false makes webpack treat a file: symlink
    // (node_modules/@rhesis/ee-frontend → ee/frontend/) as if it were
    // physically inside node_modules, so its imports walk up to
    // apps/frontend/node_modules for MUI/React — no aliases needed.
    config.resolve.symlinks = false;

    // Development-specific optimizations
    if (dev) {
      config.watchOptions = {
        poll: 500, // Reduced from 1000 for faster detection
        aggregateTimeout: 200, // Reduced from 300
        ignored: [
          '**/node_modules/**',
          '**/.git/**',
          '**/.next/**',
          '**/coverage/**',
          '**/.vscode/**',
          '**/.idea/**',
          '**/dist/**',
          '**/build/**',
        ],
      };

      config.cache = {
        type: 'filesystem',
        buildDependencies: {
          config: [__filename],
        },
        // Add timestamp to cache version to reduce stale cache issues
        version: `dev-${Date.now()}`,
        // Shorter cache duration
        maxAge: 1000 * 60 * 5, // 5 minutes instead of default
      };

      // The filesystem cache emits "PackFileCacheStrategy: Serializing big
      // strings" notices at webpack's infrastructure log level. They are a
      // harmless dev-only performance hint (not an error), so raise the
      // infrastructure log level to silence the noise while still surfacing
      // real errors. ignoreWarnings does not apply here — these are
      // infrastructure logs, not compilation warnings.
      config.infrastructureLogging = {
        ...config.infrastructureLogging,
        level: 'error',
      };

      // Reduce worker threads to prevent memory issues
      config.parallelism = 2;
    } else {
      // Production: disable caching
      config.cache = false;
    }

    // Client-side optimizations
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        crypto: false,
        stream: false,
        url: false,
        zlib: false,
        http: false,
        https: false,
        assert: false,
        os: false,
        path: false,
      };
    }

    // Performance optimizations
    config.optimization = {
      ...config.optimization,
      moduleIds: 'deterministic',
    };

    // Resolve the `@/` alias used throughout the app.
    // `@rhesis/ee-frontend` is a file: dependency and does not need an alias —
    // it is installed in node_modules and resolved normally.
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': path.resolve(__dirname, './src'),
      '~': path.resolve(__dirname, './'),
    };

    return config;
  },

  // Reduce JavaScript bundle size
  poweredByHeader: false,

  // Enable compression only in production
  compress: isProd,

  async headers() {
    const baseHeaders = [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          // Development: Disable caching for HTML pages
          ...(isDev
            ? [
                {
                  key: 'Cache-Control',
                  value: 'no-cache, no-store, must-revalidate',
                },
              ]
            : []),
        ],
      },
    ];

    // Only add aggressive caching headers in production
    if (isProd) {
      baseHeaders.push(
        {
          source: '/static/(.*)',
          headers: [
            {
              key: 'Cache-Control',
              value: 'public, max-age=31536000, immutable',
            },
          ],
        },
        {
          source: '/_next/static/(.*)',
          headers: [
            {
              key: 'Cache-Control',
              value: 'public, max-age=31536000, immutable',
            },
          ],
        }
      );
    }

    return baseHeaders;
  },
};

export default nextConfig;
