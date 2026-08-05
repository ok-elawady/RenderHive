import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  allowedDevOrigins: ["localhost:3000", "127.0.0.1:3000", "renderhive.local", "server.renderhive.local"],
  webpack: (config) => {
    if (process.env.WATCHPACK_POLLING === 'true') {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
  turbopack: {},
};

export default nextConfig;
