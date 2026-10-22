#!/bin/sh
set -eu

mkdir -p /data /config /data/uploads /data/vectorstore /data/models /data/logs

ssl_config=/etc/nginx/ssl-listen.conf
: > "$ssl_config"
if [ -f /data/ssl/ssl.crt ] && [ -f /data/ssl/ssl.key ]; then
    cat > "$ssl_config" <<'EOF'
    listen 443 ssl;
    http2 on;
    ssl_certificate     /data/ssl/ssl.crt;
    ssl_certificate_key /data/ssl/ssl.key;
EOF
fi

if [ ! -f /config/config.yaml ]; then
    cp /usr/share/mynexus/default-config.yaml /config/config.yaml
fi

exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
