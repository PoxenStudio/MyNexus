#!/bin/sh
set -eu

mkdir -p /data /config /data/uploads /data/vectorstore /data/models

if [ ! -f /config/config.yaml ]; then
    cp /usr/share/mynexus/default-config.yaml /config/config.yaml
fi

exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
