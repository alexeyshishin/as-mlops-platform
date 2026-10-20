# syntax=docker/dockerfile:1

# ---- deps -------------------------------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- build (Next.js static export -> /app/out) -------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Static export bakes NEXT_PUBLIC_* in at build time (no server to read env
# at runtime) — override with --build-arg for a different backend per env.
ARG NEXT_PUBLIC_API_URL=https://api.alexshishin.ru
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# ---- runtime: serve the static export with nginx -----------------------
FROM nginx:1.27-alpine AS runner
COPY --from=build /app/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
