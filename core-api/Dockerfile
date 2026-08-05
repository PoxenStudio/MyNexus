FROM golang:1.25-alpine AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -o /app/server ./cmd/mynexus-api

FROM alpine:3.20

ARG VERSION=dev
LABEL org.opencontainers.image.title="mynexus-core-api" \
      org.opencontainers.image.description="MyNexus Core API - Go + Gin backend" \
      org.opencontainers.image.authors="poxenstudio <poxenstudio@gmail.com>" \
      org.opencontainers.image.vendor="poxenstudio" \
      org.opencontainers.image.version="${VERSION}" \
      maintainer="poxenstudio <poxenstudio@gmail.com>"

RUN apk add --no-cache tzdata

ENV TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    PUID=1000 \
    PGID=1000

WORKDIR /app
COPY --from=build /app/server /app/server
EXPOSE 8080
EXPOSE 9090
CMD ["/app/server"]
