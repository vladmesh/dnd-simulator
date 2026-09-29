# Production build of the web UI, served by nginx.
# nginx proxies /api (REST + the game WebSocket) and /health to $BACKEND_URL,
# the same routes the Vite dev server proxies in vite.config.ts.

FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# The nginx image renders /etc/nginx/templates/*.template into /etc/nginx/conf.d/
# with envsubst at start-up, substituting only variables defined in the environment.
ENV BACKEND_URL=http://backend:8001
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=2s --timeout=5s --retries=10 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
