import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  allowedDevOrigins: ["localhost:3000", "127.0.0.1:3000", "renderhive.local", "server.renderhive.local"],
  async rewrites() {
    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
    return [
      { source: '/api/:path*', destination: `${apiUrl}/api/:path*` },
      { source: '/_allauth/:path*', destination: `${apiUrl}/_allauth/:path*` },
      { source: '/admin/:path*', destination: `${apiUrl}/admin/:path*` },
      { source: '/static/:path*', destination: `${apiUrl}/static/:path*` },
      { source: '/media/:path*', destination: `${apiUrl}/media/:path*` },
    ];
  },
};

export default nextConfig;
