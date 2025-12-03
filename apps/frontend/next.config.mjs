// Set memory limit to prevent swapping
process.env.NODE_OPTIONS = '--max-old-space-size=4096';

import path from 'path';
import { fileURLToPath } from 'url';
import { readFileSync } from 'fs';
import { execSync } from 'child_process';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Function to get git information
function getGitInfo() {
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

  // Compiler optimizations
  compiler: {
    // Remove console.log in production only
    removeConsole: isProd,
  },

  // Source maps: enable in prod for debugging, faster option in dev
  productionBrowserSourceMaps: isProd,

  // Experimental features
  experimental: {
    // Enable optimized package imports for MUI and other heavy libraries
    optimizePackageImports: [
      '@mui/material',
      '@mui/icons-material',
      '@mui/x-data-grid',
      '@mui/x-date-pickers',
      '@toolpad/core',
      'lucide-react',
      'date-fns',
      'lodash',
    ],
  },

  // Environment variables available to the client
  env: {
    APP_VERSION: JSON.parse(
      readFileSync(path.join(__dirname, 'package.json'), 'utf8')
    ).version,
    ...(() => {
      const gitInfo = getGitInfo();
      return {
        GIT_BRANCH: gitInfo.branch,
        GIT_COMMIT: gitInfo.commit,
      };
    })(),
  },

  // API rewrites for cross-container communication
  async rewrites() {
    // Use BACKEND_URL for server-side calls (container-to-container)
    // Use NEXT_PUBLIC_API_BASE_URL for client-side calls (browser-to-host)
    const backendUrl = process.env.BACKEND_URL || 'http://backend:8080';
    return [
      // Exclude NextAuth.js routes from being proxied (keep them local)
      {
        source: '/api/auth/:path*',
        destination: '/api/auth/:path*',
      },
      // Proxy all other API calls to backend
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },

  // Development-specific: configure on-demand entries to reduce caching
  ...(isDev && {
    onDemandEntries: {
      // Shorter period to keep pages in buffer
      maxInactiveAge: 15 * 1000, // 15 seconds instead of default 60
      // Fewer pages kept simultaneously
      pagesBufferLength: 2,
    },
  }),

  // Turbopack configuration
  turbopack: {
    rules: {
      '*.svg': {
        loaders: ['@svgr/webpack'],
        as: '*.js',
      },
    },
  },

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

  // Webpack optimizations
  webpack: (config, { dev, isServer }) => {
    // Your existing markdown rule
    config.module.rules.push({
      test: /\.md$/,
      type: 'asset/source',
    });

    // Development-specific optimizations
    if (dev) {
      // Use faster source map option
      config.devtool = 'eval-cheap-module-source-map';

      // MODIFIED: More aggressive file watching for better change detection
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

      // Optimize module resolution
      config.resolve.symlinks = false;

      // MODIFIED: Less aggressive caching for development
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

    // Resolve optimizations
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': path.resolve(__dirname, './'),
      '~': path.resolve(__dirname, './'),
    };

    config.resolve.modules = [
      'node_modules',
      path.resolve(__dirname, 'node_modules'),
    ];
    config.resolve.extensions = ['.js', '.jsx', '.ts', '.tsx', '.json'];

    return config;
  },

  // Reduce JavaScript bundle size
  poweredByHeader: false,

  // Enable compression only in production
  compress: isProd,

  // MODIFIED: Headers with environment-specific caching
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
