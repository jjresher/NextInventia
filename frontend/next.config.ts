import type { NextConfig } from "next";
import { createSecurityHeaders } from "./src/lib/securityHeaders.mjs";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: createSecurityHeaders({
          apiUrl: process.env.NEXT_PUBLIC_API_URL,
          isProduction: process.env.NODE_ENV === "production",
        }),
      },
    ];
  },
};

export default nextConfig;
