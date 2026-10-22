#!/bin/sh
set -eu

PUID=${PUID:-1000}
PGID=${PGID:-1000}

if [ "$(id -g nexus)" != "$PGID" ]; then
    groupmod -o -g "$PGID" nexus
fi
if [ "$(id -u nexus)" != "$PUID" ]; then
    usermod -o -u "$PUID" nexus
fi

chown -R nexus:nexus /home/nexus /run/nginx /var/cache/nginx /var/lib/nginx

mkdir -p /data /config /data/uploads /data/vectorstore /data/models /data/logs

for permission_dir in /data /config; do
    permission_file="$permission_dir/.permission"
    touch "$permission_file"
    if [ "$(cat "$permission_file")" != "$PUID:$PGID" ]; then
        echo "Updating $permission_dir ownership to $PUID:$PGID"
        chown -R nexus:nexus "$permission_dir"
        printf '%s:%s\n' "$PUID" "$PGID" > "$permission_file"
    fi
done

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

exec /usr/bin/supervisord -n -u root -c /etc/supervisor/supervisord.conf
