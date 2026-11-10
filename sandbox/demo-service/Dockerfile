# Newest Node.js 24 patch on Alpine 3.24, a minimal OS that Amazon Inspector supports
# for ECR scanning. Pin the Alpine release: the unversioned -alpine tag moves to new
# releases, and Inspector stops reporting OS findings for discontinued ones.
FROM node:24.22.2-alpine3.24 AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM node:24.22.2-alpine3.24

# npm is only needed to install dependencies. Its bundled packages (undici, glob, ...)
# carry their own vulnerabilities, so it is removed from the runtime image.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx

# The base image still ships zlib 1.3.2 (CVE-2026-4738); the fix 1.4-r0 is already in
# the Alpine 3.24 repository. Drop this once a newer base image includes it.
RUN apk upgrade --no-cache zlib

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src

USER node
EXPOSE 3000
CMD ["node", "src/server.js"]
