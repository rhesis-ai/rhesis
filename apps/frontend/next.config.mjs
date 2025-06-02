// Set memory limit to prevent swapping
process.env.NODE_OPTIONS = '--max-old-space-size=4096';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Compiler optimizations
  compiler: {
    // Remove console.log in production
    removeConsole: process.env.NODE_ENV === 'production',
  },
  
  // Keep source maps in production for debugging, disable in dev for speed
  productionBrowserSourceMaps: true,
  
  // Experimental features for better performance
  experimental: {
    // Enable optimized package imports for MUI and other heavy libraries
    optimizePackageImports: [
      '@mui/material',
      '@mui/icons-material', 
      '@mui/x-data-grid',
      '@mui/x-date-pickers',
      '@toolpad/core',
      '@monaco-editor/react',
      'lucide-react', 
      'date-fns',
      'lodash'
    ],

    // Additional performance optimizations
    optimizeServerReact: true,
    optimizeCss: true,
  },

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
    // Disable optimization in development for faster builds
    unoptimized: process.env.NODE_ENV === 'development',
    // Reduce formats for faster processing
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
      // Use faster source map option instead of disabling completely
      config.devtool = 'eval-cheap-module-source-map';
      
      // Optimized file watching
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
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
      
      // Cache configuration for faster rebuilds
      config.cache = {
        type: 'filesystem',
        buildDependencies: {
          config: [__filename],
        },
        // Add cache versioning
        version: '1.0.0',
      };

      // Reduce worker threads to prevent memory issues
      config.parallelism = 2;
    }

    // Client-side optimizations
    if (!isServer) {
      // Exclude server-side modules from client bundle
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
      splitChunks: {
        chunks: 'all',
        maxInitialRequests: 25,
        minSize: 20000,
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            priority: 10,
            reuseExistingChunk: true,
          },
          mui: {
            test: /[\\/]node_modules[\\/]@mui[\\/]/,
            name: 'mui',
            priority: 15,
            reuseExistingChunk: true,
          },
          common: {
            name: 'common',
            minChunks: 2,
            priority: 5,
            reuseExistingChunk: true,
          },
        },
      },
    };

    // Resolve optimizations
    config.resolve.alias = {
      ...config.resolve.alias,
      // Add common aliases to speed up resolution
      '@': require('path').resolve(__dirname, './'),
      '~': require('path').resolve(__dirname, './'),
      // Use ESM versions for better tree shaking
      '@mui/icons-material': '@mui/icons-material/esm',
    };

    // Module resolution optimizations
    config.resolve.modules = ['node_modules', require('path').resolve(__dirname, 'node_modules')];

    // Faster module resolution
    config.resolve.extensions = ['.js', '.jsx', '.ts', '.tsx', '.json'];

    return config;
  },

  // Reduce JavaScript bundle size
  poweredByHeader: false,
  
  // Compression settings
  compress: true,
  
  // Output settings for better caching
  output: 'standalone',
  
  // Headers for better caching
  async headers() {
    return [
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
        ],
      },
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
      },
    ];
  },
};

export default nextConfig;