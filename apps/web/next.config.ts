import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The shared-schemas workspace package ships TypeScript source, so Next must
  // transpile it.
  transpilePackages: ['@researchos/shared-schemas'],
};

export default nextConfig;
