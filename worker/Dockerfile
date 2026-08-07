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
# Pre-download the NLTK model data English keyword extraction needs
# (util/keywords.py's _extract_en) at build time — the worker's runtime
# environment isn't assumed to have internet access, so this can't be
# fetched lazily on first use like it normally would be.
RUN python3 -m nltk.downloader -d "$NLTK_DATA" punkt_tab averaged_perceptron_tagger_eng
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
