import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  allowedDevOrigins: ['renderhive.local', 'api.renderhive.local'],
};

export default nextConfig;
