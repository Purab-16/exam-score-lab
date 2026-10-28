import type { NextConfig } from "next";

// Security headers. Read when the app is built, so set these as build settings
// (for Docker: build arguments, see web/Dockerfile and docker-compose.yml).
//
//   WEB_SECURITY_HEADERS  true (default) | false   all headers below
//   CSP_MODE              enforce | report-only | off
//                         default: enforce for production builds, report-only for `next dev`
//   HSTS_MAX_AGE          seconds, default 86400 (one day), 0 turns it off
//                         Short on purpose: browsers remember HSTS and it is hard to undo.
//                         Raise it only once HTTPS is working everywhere.

const isDev = process.env.NODE_ENV === "development";

const text = (name: string) => process.env[name]?.trim() || undefined;

function flag(name: string, fallback: boolean): boolean {
  const raw = text(name)?.toLowerCase();
  if (raw === undefined) return fallback;
  if (["1", "true", "yes", "on"].includes(raw)) return true;
  if (["0", "false", "no", "off"].includes(raw)) return false;
  throw new Error(`${name} must be true or false, got "${raw}"`);
}

type CspMode = "enforce" | "report-only" | "off";

function cspMode(): CspMode {
  const raw = text("CSP_MODE")?.toLowerCase();
  if (raw === undefined) return isDev ? "report-only" : "enforce";
  if (raw === "enforce" || raw === "report-only" || raw === "off") return raw;
  throw new Error(`CSP_MODE must be enforce, report-only or off, got "${raw}"`);
}

function hstsMaxAge(): number {
  const raw = text("HSTS_MAX_AGE");
  if (raw === undefined) return 86400;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) throw new Error(`HSTS_MAX_AGE must be a whole number of seconds, got "${raw}"`);
  return value;
}

/** Where the browser may send requests: this site, plus the API when it lives on another origin. */
function connectSources(): string {
  const api = (text("NEXT_PUBLIC_API_URL") ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const sources = ["'self'"];
  if (!api.startsWith("/")) sources.push(new URL(api).origin); // "/api" (one origin behind a proxy) needs nothing extra
  if (isDev) sources.push("ws:", "wss:"); // hot reload
  return sources.join(" ");
}

// 'unsafe-inline' is needed for the inline scripts Next.js and next-themes add and for chart styles.
// A nonce would avoid it, but forces every page to render per request (and breaks Partial Prerendering).
// This policy still blocks other origins, plugins, framing and form posts elsewhere.
function contentSecurityPolicy(): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src ${connectSources()}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

function securityHeaders() {
  if (!flag("WEB_SECURITY_HEADERS", true)) return [];

  const headers = [
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  ];

  const hsts = hstsMaxAge();
  if (hsts > 0) headers.push({ key: "Strict-Transport-Security", value: `max-age=${hsts}` });

  const mode = cspMode();
  if (mode !== "off") {
    headers.push({
      key: mode === "report-only" ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy",
      value: contentSecurityPolicy(),
    });
  }
  return headers;
}

const nextConfig: NextConfig = {
  // Self-contained server in .next/standalone for the Docker image
  output: "standalone",
  // Do not announce the framework in every response
  poweredByHeader: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    const headers = securityHeaders();
    return headers.length ? [{ source: "/:path*", headers }] : [];
  },
};

export default nextConfig;
