import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next blocks dev resources (including the HMR socket) for any host it was not
  // started on. Reaching the dev server by IP without this leaves the page served
  // but never hydrated - it renders the loading skeleton forever and issues no
  // API calls at all.
  allowedDevOrigins: ["127.0.0.1"],
  // Both of these stop Next walking up past the repo and adopting a stray lockfile
  // in $HOME as the project root.
  turbopack: { root: import.meta.dirname },
  outputFileTracingRoot: import.meta.dirname,
};

export default nextConfig;
