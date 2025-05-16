/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.googleusercontent.com',
        pathname: '**',
      },
      // Keep other patterns if they exist
    ],
    unoptimized: process.env.NODE_ENV === 'development', // Optional: disable optimization in development
  },
  webpack: (config) => {
    config.module.rules.push({
      test: /\.md$/,
      type: 'asset/source'
    });
    return config;
  }
};

export default nextConfig;
