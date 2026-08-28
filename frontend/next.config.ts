import type { NextConfig } from "next";

const isExport = process.env.NEXT_EXPORT === "true";

const nextConfig: NextConfig = {
  output: isExport ? "export" : undefined,
  trailingSlash: isExport ? true : false,
  images: {
    unoptimized: isExport ? true : false,
  },
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
