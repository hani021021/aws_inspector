# Newest Node.js 24 patch. Debian OS packages still produce findings that have no fix yet.
FROM node:24.22.2-trixie-slim AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM node:24.22.2-trixie-slim

# npm is only needed to install dependencies. Its bundled packages (undici, glob, ...)
# carry their own vulnerabilities, so it is removed from the runtime image.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src

USER node
EXPOSE 3000
CMD ["node", "src/server.js"]
