FROM python:3.12-alpine

ARG VERSION=dev
LABEL org.opencontainers.image.title="mynexus-worker" \
      org.opencontainers.image.description="MyNexus Worker - Python capability node (parse/clean/split/embed/retrieve/LLM)" \
      org.opencontainers.image.authors="poxenstudio <poxenstudio@gmail.com>" \
      org.opencontainers.image.vendor="poxenstudio" \
      org.opencontainers.image.version="${VERSION}" \
      maintainer="poxenstudio <poxenstudio@gmail.com>"

RUN apk add --no-cache tzdata

ENV TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    PUID=1000 \
    PGID=1000 \
    NLTK_DATA=/usr/share/nltk_data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bundled font for util/cover_generator.py's title-based fallback cover —
# baked in so cover generation works out of the box with no deploy-time
# step; a deployer can still override it by dropping a font at
# data/fonts/MiSans-Normal.woff (shared bind mount, see docker-compose.yml)
# or via config.yaml's cover.font_path, without rebuilding this image.
COPY assets ./assets
COPY src ./src
WORKDIR /app/src
EXPOSE 8001
CMD ["python3", "server.py"]
