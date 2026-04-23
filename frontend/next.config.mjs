/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

const nextConfig = {
  async redirects() {
    return [
      {
        source: '/',
        destination: '/landing',
        permanent: false,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/:path*`,
      },
      {
        source: '/outputs/:path*',
        destination: `${BACKEND_URL}/outputs/:path*`,
      },
      {
        source: '/feed/:path*',
        destination: `${BACKEND_URL}/feed/:path*`,
      },
    ];
  },
};

export default nextConfig;
