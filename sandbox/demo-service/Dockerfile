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

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src

USER node
EXPOSE 3000
CMD ["node", "src/server.js"]
