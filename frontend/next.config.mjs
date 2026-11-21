/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

const nextConfig = {
  // The studio is the app: it lives at "/". The marketing page is at "/landing".
  // A redirect from "/" to "/landing" would shadow the studio route entirely.
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
