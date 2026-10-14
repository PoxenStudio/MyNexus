FROM golang:1.25-alpine AS core-build
ENV GOPROXY=https://goproxy.cn,direct
WORKDIR /src/core-api
COPY core-api/go.mod core-api/go.sum ./
RUN go mod download
COPY core-api/cmd ./cmd
COPY core-api/internal ./internal
RUN CGO_ENABLED=0 go build -o /out/mynexus-api ./cmd/mynexus-api

FROM node:20-alpine AS web-build
WORKDIR /src/web-ui
COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm ci
COPY web-ui/ ./
RUN npm run build

FROM python:3.12-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="MyNexus" \
      org.opencontainers.image.description="Integrated MyNexus application image" \
      org.opencontainers.image.authors="poxenstudio <poxenstudio@gmail.com>" \
      org.opencontainers.image.vendor="poxenstudio" \
      org.opencontainers.image.version="${VERSION}" \
      maintainer="poxenstudio <poxenstudio@gmail.com>"

ENV TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    NLTK_DATA=/usr/share/nltk_data \
    MYNEXUS_CONFIG_PATH=/config/config.yaml \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir -r /app/worker/requirements.txt \
    && mkdir -p "$NLTK_DATA"

COPY --from=core-build /out/mynexus-api /app/mynexus-api
COPY --from=web-build /src/web-ui/dist /usr/share/nginx/html
COPY data/nltk/ /usr/share/nltk_data/
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
