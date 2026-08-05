FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine

ARG VERSION=dev
LABEL org.opencontainers.image.title="mynexus-webui" \
      org.opencontainers.image.description="MyNexus Web UI - Vue3 + TypeScript + Vite frontend" \
      org.opencontainers.image.authors="poxenstudio <poxenstudio@gmail.com>" \
      org.opencontainers.image.vendor="poxenstudio" \
      org.opencontainers.image.version="${VERSION}" \
      maintainer="poxenstudio <poxenstudio@gmail.com>"

RUN apk add --no-cache tzdata

ENV TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    PUID=1000 \
    PGID=1000

COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
