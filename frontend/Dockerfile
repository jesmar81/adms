# Production image: standalone Next.js output, non-root runtime.
FROM node:24-alpine AS deps
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS builder
WORKDIR /srv/web
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /srv/web
ENV NODE_ENV=production
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /srv/web/.next/standalone ./
COPY --from=builder /srv/web/.next/static ./.next/static
USER app
EXPOSE 3000
CMD ["node", "server.js"]
