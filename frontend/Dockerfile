FROM node:22-alpine AS builder

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . ./
RUN pnpm build

# ----

FROM nginx:1.27-alpine AS runtime

# Replace default nginx config
RUN rm /etc/nginx/conf.d/default.conf
COPY <<'EOF' /etc/nginx/conf.d/app.conf
server {
  listen 80 default_server;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  # Long-cache hashed assets
  location ~* \.(?:css|js|woff2|svg|png|jpg|jpeg|gif|ico)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
  }

  # SPA fallback for client-side routes
  location / {
    try_files $uri $uri/ /index.html;
  }
}
EOF

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1/ > /dev/null || exit 1
