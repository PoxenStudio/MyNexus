ARG BASE_IMAGE=docker.1ms.run/poxenstudio/mynexus_base:latest

FROM docker.1ms.run/golang:1.25-alpine AS core-build
ENV GOPROXY=https://goproxy.cn,direct
WORKDIR /src/core-api
COPY core-api/go.mod core-api/go.sum ./
RUN go mod download
COPY core-api/cmd ./cmd
COPY core-api/internal ./internal

RUN CGO_ENABLED=0 go build -o /out/mynexus-api ./cmd/mynexus-api
FROM docker.1ms.run/node:20-alpine AS web-build
WORKDIR /src/web-ui
COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && \
    npm ci
COPY web-ui/ ./
RUN npm run build

FROM ${BASE_IMAGE}

ARG VERSION=dev
LABEL org.opencontainers.image.title="MyNexus" \
      org.opencontainers.image.description="Integrated MyNexus application image" \
      org.opencontainers.image.authors="poxenstudio <poxenstudio@gmail.com>" \
      org.opencontainers.image.vendor="poxenstudio" \
      org.opencontainers.image.version="${VERSION}" \
      maintainer="poxenstudio <poxenstudio@gmail.com>"

ENV MYNEXUS_CONFIG_PATH=/config/config.yaml

WORKDIR /app

COPY --from=core-build /out/mynexus-api /app/mynexus-api
COPY --from=web-build /src/web-ui/dist /usr/share/nginx/html
COPY worker/assets /app/assets
COPY worker/src /app/worker/src
COPY docker/default-config.yaml /usr/share/mynexus/default-config.yaml
COPY docker/nginx.conf /etc/nginx/sites-available/default
COPY docker/supervisord.conf /etc/supervisor/conf.d/mynexus.conf
COPY docker/entrypoint.sh /usr/local/bin/mynexus-entrypoint

RUN chmod +x /usr/local/bin/mynexus-entrypoint \
    && mkdir -p /data /config /run/nginx

EXPOSE 80
ENTRYPOINT ["/usr/local/bin/mynexus-entrypoint"]
