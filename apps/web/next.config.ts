import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The development badge overlaps the compact workspace rail and is not part
  // of the ResearchOS product UI. Errors remain available in the terminal.
  devIndicators: false,
  // The shared-schemas workspace package ships TypeScript source, so Next must
  // transpile it.
  transpilePackages: ['@researchos/shared-schemas'],
};

export default nextConfig;
