import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  env: {
    NEXT_PUBLIC_DJANGO_API_URL: process.env.DJANGO_API_URL || "",
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.DJANGO_API_URL || "http://localhost:8000"}/api/:path*/`,
      },
    ];
  },
};

export default nextConfig;