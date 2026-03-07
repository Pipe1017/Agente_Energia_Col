# ============================================================
# Agente Energia Col — Frontend Dockerfile
# Multi-stage: build (Node) → serve (nginx)
# ============================================================

# ------------------------------------------------------------
# Stage 1: build con Node.js
# ------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Instalar dependencias primero (mejor cache de capas)
COPY package.json package-lock.json* ./
RUN npm ci

# Copiar código fuente y construir
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ------------------------------------------------------------
# Stage 2: servir con nginx
# ------------------------------------------------------------
FROM nginx:alpine AS production

# Configuración nginx para SPA (React Router)
COPY --from=builder /app/dist /usr/share/nginx/html

RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    location /api {\n\
        proxy_pass http://api:8000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -qO- http://127.0.0.1/ || exit 1
