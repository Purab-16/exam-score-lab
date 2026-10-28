# nginx for docker-compose.proxy.yml: the official unprivileged image, pinned to one version, with the
# three Alpine packages that have a security fix upgraded (found by Trivy on 2026-10-28).
# Only those packages are upgraded, so the nginx version does not change by accident.
# When a newer base image already has the fixes, this file can go and the compose file can use the image directly.
FROM nginxinc/nginx-unprivileged:1.30.6-alpine

USER root
RUN apk upgrade --no-cache brotli-libs curl libcurl
USER nginx
