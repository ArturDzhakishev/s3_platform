# ── Frontend Dockerfile ───────────────────────────────────────────────────────
# Этап 1 — сборка React-приложения
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --silent

COPY . .

# VITE_BACKEND_URL передаётся как build arg — встраивается в итоговый bundle
ARG VITE_BACKEND_URL=http://localhost:8000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

RUN npm run build


# Этап 2 — Nginx для раздачи статики
FROM nginx:1.27-alpine

# Удалить дефолтный конфиг nginx
RUN rm /etc/nginx/conf.d/default.conf

# Наш конфиг: раздача статики + proxy /api → backend
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Скопировать собранный React-проект
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]