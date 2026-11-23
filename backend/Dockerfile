FROM node:22-bookworm-slim AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
RUN npm ci
COPY prisma ./prisma
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/*
ADD --chmod=0444 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /app/rds-ca.pem
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --omit=peer --omit=optional --ignore-scripts \
    && test ! -d node_modules/prisma
COPY --from=build /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=build /app/dist ./dist
USER node

FROM runtime AS api
EXPOSE 4000
CMD ["node", "dist/api.js"]

FROM runtime AS worker
CMD ["node", "dist/worker.js"]
