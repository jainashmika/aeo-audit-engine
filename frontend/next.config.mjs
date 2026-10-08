/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker uses the standalone server; Netlify's Next.js runtime packages the app itself.
  output: process.env.NETLIFY ? undefined : "standalone",
  reactStrictMode: true,
};
export default nextConfig;
