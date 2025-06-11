// Set memory limit to prevent swapping
process.env.NODE_OPTIONS = '--max-old-space-size=4096';

import path from 'path';
import { fileURLToPath } from 'url';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isDev = process.env.NODE_ENV === 'development';
const isProd = process.env.NODE_ENV === 'production';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // ===== DEVELOPMENT-SPECIFIC ANTI-CACHING =====
  // These are the key additions to fix your caching issues
  generateEtags: !isDev, // Disable ETags in development
  
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
      'lodash'
    ],
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
  webpack: (config, { dev, isServer, webpack }) => {
    // Your existing markdown rule
    config.module.rules.push({
      test: /\.md$/,
      type: 'asset/source'
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
      // Production: more aggressive caching
      config.cache = {
        type: 'filesystem',
        buildDependencies: {
          config: [__filename],
        },
        version: '1.0.0',
      };
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

    config.resolve.modules = ['node_modules', path.resolve(__dirname, 'node_modules')];
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
          ...(isDev ? [{
            key: 'Cache-Control',
            value: 'no-cache, no-store, must-revalidate',
          }] : []),
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