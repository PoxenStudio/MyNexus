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
    PGID=1000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
WORKDIR /app/src
EXPOSE 8001
CMD ["python3", "server.py"]
