# Web image. Build from the web/ folder:
#   docker build -t exam-score-web --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 .
# NEXT_PUBLIC_API_URL is baked into the browser bundle at build time, so it must be the API URL
# as seen from the user's browser, not from inside Docker.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# public/ holds static files (images, robots.txt). Git does not track an empty folder, so create it
# here: the final stage copies it, and a fresh clone without public/ must still build.
RUN mkdir -p public
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
# Security header settings, read when the app is built (see next.config.ts). Empty means the default.
ARG WEB_SECURITY_HEADERS=
ARG CSP_MODE=
ARG HSTS_MAX_AGE=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    WEB_SECURITY_HEADERS=$WEB_SECURITY_HEADERS \
    CSP_MODE=$CSP_MODE \
    HSTS_MAX_AGE=$HSTS_MAX_AGE \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The app only runs `node server.js`. npm, npx and yarn come with the base image, are not needed at run
# time, and the libraries bundled inside npm were flagged by security scanners (11 HIGH findings).
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
 && rm -rf /opt/yarn-* /usr/local/bin/yarn /usr/local/bin/yarnpkg

# The standalone server does not serve public/ or .next/static unless they are copied next to it
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -q -O /dev/null "http://127.0.0.1:${PORT}/" || exit 1
CMD ["node", "server.js"]
